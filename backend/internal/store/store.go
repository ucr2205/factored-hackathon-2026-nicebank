// Package store wraps the Postgres pool. Every query on customer data runs inside WithCustomer, which pins
// the transaction to one customer via `SET LOCAL app.customer_id`, so row-level security applies. The pin is
// computed inside Postgres from the token's opaque customer_ref, so the backend never handles the bank id.
//
// Pipeline role: every turn runs in one WithCustomer transaction, so Understand, Decide, Act, Verify and the
// audit rows commit or roll back together. Staff routes use WithStaff, which pins the staff role and username
// for the staff row-level security policies instead of a customer.
package store

import (
	"context"
	"errors"
	"net/netip"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Store is the shared Postgres pool used by the API and the notification worker.
type Store struct{ Pool *pgxpool.Pool }

// Open connects the pool for url (DATABASE_URL).
func Open(ctx context.Context, url string) (*Store, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	return &Store{Pool: pool}, nil
}

// Close releases the pool.
func (s *Store) Close() { s.Pool.Close() }

// ErrNoCustomer means the token's customer_ref is empty or resolves to no customer.
var ErrNoCustomer = errors.New("token has no known customer_ref")

type clientIPKey struct{}

// WithClientIP returns ctx carrying the caller's IP as the HTTP layer validated it (TRUSTED_PROXIES rules).
// WithCustomer and WithStaff pin it as app.client_ip, which audit_events.client_ip takes by default, so every
// audit row written in the request (by Go or by a SECURITY DEFINER function) records where it came from.
func WithClientIP(ctx context.Context, ip string) context.Context {
	return context.WithValue(ctx, clientIPKey{}, ip)
}

// clientIP returns the context's IP in canonical form, or "" when absent or not an IP (never a raw header).
func clientIP(ctx context.Context) string {
	ip, _ := ctx.Value(clientIPKey{}).(string)
	if addr, err := netip.ParseAddr(ip); err == nil {
		return addr.Unmap().String()
	}
	return ""
}

// WithCustomer runs fn in a transaction scoped to the customer behind customerRef (from the verified token).
// An unknown ref pins nothing and fails, so it can never fall through to another customer's rows.
func (s *Store) WithCustomer(ctx context.Context, customerRef string, fn func(pgx.Tx) error) error {
	if customerRef == "" {
		return ErrNoCustomer
	}
	return pgx.BeginFunc(ctx, s.Pool, func(tx pgx.Tx) error {
		var pinned, ip string
		if err := tx.QueryRow(ctx, "SELECT set_config('app.customer_id', coalesce(resolve_customer($1), ''), true), "+
			"set_config('app.client_ip', $2, true)", customerRef, clientIP(ctx)).Scan(&pinned, &ip); err != nil {
			return err
		}
		if pinned == "" {
			return ErrNoCustomer
		}
		return fn(tx)
	})
}

// WithStaff runs fn in a transaction scoped to a staff role ("agent" or "supervisor") and staff username.
func (s *Store) WithStaff(ctx context.Context, role, username string, fn func(pgx.Tx) error) error {
	if role != "agent" && role != "supervisor" {
		return errors.New("invalid staff role")
	}
	return pgx.BeginFunc(ctx, s.Pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT set_config('app.staff_role', $1, true), set_config('app.staff_user', $2, true), "+
			"set_config('app.client_ip', $3, true)", role, username, clientIP(ctx)); err != nil {
			return err
		}
		return fn(tx)
	})
}
