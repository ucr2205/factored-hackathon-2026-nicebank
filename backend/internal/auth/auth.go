// Package auth verifies Keycloak access tokens and exposes the caller as a Principal.
// The customer identity comes only from the verified token, never from request bodies or model output.
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

type Principal struct {
	Subject    string
	Username   string
	CustomerID string
	Roles      []string
	ACR        int // level of authentication: 1 = password, 2 = password + TOTP
}

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

func FromContext(ctx context.Context) (Principal, bool) {
	p, ok := ctx.Value(ctxKey{}).(Principal)
	return p, ok
}

func WithPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, ctxKey{}, p)
}

type Verifier struct{ v *oidc.IDTokenVerifier }

// NewVerifier checks signature (keys from jwksURL), issuer, audience and expiry.
func NewVerifier(ctx context.Context, issuer, jwksURL, audience string) *Verifier {
	keys := oidc.NewRemoteKeySet(ctx, jwksURL)
	return &Verifier{v: oidc.NewVerifier(issuer, keys, &oidc.Config{ClientID: audience})}
}

var ErrUnauthorized = errors.New("unauthorized")

func (v *Verifier) Verify(ctx context.Context, raw string) (Principal, error) {
	tok, err := v.v.Verify(ctx, raw)
	if err != nil {
		return Principal{}, ErrUnauthorized
	}
	var claims struct {
		Username    string `json:"preferred_username"`
		CustomerID  string `json:"customer_id"`
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
		Subject: tok.Subject, Username: claims.Username, CustomerID: claims.CustomerID,
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
