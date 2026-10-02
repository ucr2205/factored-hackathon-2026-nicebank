// Package auth verifies Keycloak access tokens and exposes the caller as a Principal.
// The customer identity comes only from the verified token, never from request bodies or model output. The
// token carries an opaque customer_ref, not the bank's customer_id; Postgres resolves it per transaction.
//
// Pipeline role: runs before every turn. The Principal it produces decides which customer's rows a turn can see
// (via store.WithCustomer) and whether an action that needs step-up (acr >= 2) may run.
package auth

import (
	"context"
	"errors"
	"net/http"
	"slices"
	"strconv"
	"strings"

	"github.com/coreos/go-oidc/v3/oidc"
)

// Principal is the authenticated caller, built only from verified token claims.
type Principal struct {
	Subject     string
	Username    string
	CustomerRef string // opaque pseudonym from the token; see store.WithCustomer
	Roles       []string
	ACR         int // level of authentication: 1 = password, 2 = password + TOTP
}

// HasRole reports whether the token's realm roles include role.
func (p Principal) HasRole(role string) bool { return slices.Contains(p.Roles, role) }

// StaffRole returns the highest staff role, or "" for customers.
func (p Principal) StaffRole() string {
	switch {
	case p.HasRole("supervisor"):
		return "supervisor"
	case p.HasRole("agent"):
		return "agent"
	}
	return ""
}

type ctxKey struct{}

// FromContext returns the Principal stored by Middleware, if any.
func FromContext(ctx context.Context) (Principal, bool) {
	p, ok := ctx.Value(ctxKey{}).(Principal)
	return p, ok
}

// WithPrincipal returns ctx carrying p (used by Middleware and tests).
func WithPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, ctxKey{}, p)
}

// Verifier validates bearer tokens against the Keycloak realm's signing keys.
type Verifier struct{ v *oidc.IDTokenVerifier }

// NewVerifier checks signature (keys from jwksURL), issuer, audience and expiry.
func NewVerifier(ctx context.Context, issuer, jwksURL, audience string) *Verifier {
	keys := oidc.NewRemoteKeySet(ctx, jwksURL)
	return &Verifier{v: oidc.NewVerifier(issuer, keys, &oidc.Config{ClientID: audience})}
}

// ErrUnauthorized is returned for any invalid, expired or unparsable token; the cause is not exposed.
var ErrUnauthorized = errors.New("unauthorized")

// Verify checks a raw access token and maps its claims (preferred_username, customer_ref, acr, realm roles)
// to a Principal. A missing or non-numeric acr becomes 0.
func (v *Verifier) Verify(ctx context.Context, raw string) (Principal, error) {
	tok, err := v.v.Verify(ctx, raw)
	if err != nil {
		return Principal{}, ErrUnauthorized
	}
	var claims struct {
		Username    string `json:"preferred_username"`
		CustomerRef string `json:"customer_ref"`
		ACR         string `json:"acr"`
		RealmAccess struct {
			Roles []string `json:"roles"`
		} `json:"realm_access"`
	}
	if err := tok.Claims(&claims); err != nil {
		return Principal{}, ErrUnauthorized
	}
	acr, _ := strconv.Atoi(claims.ACR)
	return Principal{
		Subject: tok.Subject, Username: claims.Username, CustomerRef: claims.CustomerRef,
		Roles: claims.RealmAccess.Roles, ACR: acr,
	}, nil
}

// Middleware rejects requests without a valid bearer token.
func (v *Verifier) Middleware(onError func(http.ResponseWriter, int, string, string)) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			raw, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
			if !ok || raw == "" {
				onError(w, http.StatusUnauthorized, "unauthorized", "missing bearer token")
				return
			}
			p, err := v.Verify(r.Context(), raw)
			if err != nil {
				onError(w, http.StatusUnauthorized, "unauthorized", "invalid or expired token")
				return
			}
			next.ServeHTTP(w, r.WithContext(WithPrincipal(r.Context(), p)))
		})
	}
}

// RequireAnyRole allows the request only if the principal has one of the roles.
func RequireAnyRole(onError func(http.ResponseWriter, int, string, string), roles ...string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			p, _ := FromContext(r.Context())
			if !slices.ContainsFunc(roles, p.HasRole) {
				onError(w, http.StatusForbidden, "forbidden", "role not allowed")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
