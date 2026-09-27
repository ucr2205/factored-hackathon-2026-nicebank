// Package store wraps the Postgres pool. Every query on customer data runs inside WithCustomer, which pins
// the transaction to one customer via `SET LOCAL app.customer_id`, so row-level security applies.
package store

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct{ Pool *pgxpool.Pool }

func Open(ctx context.Context, url string) (*Store, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	return &Store{Pool: pool}, nil
}

func (s *Store) Close() { s.Pool.Close() }

var ErrNoCustomer = errors.New("token has no customer_id")

// WithCustomer runs fn in a transaction scoped to customerID (taken from the verified token).
func (s *Store) WithCustomer(ctx context.Context, customerID string, fn func(pgx.Tx) error) error {
	if customerID == "" {
		return ErrNoCustomer
	}
	return pgx.BeginFunc(ctx, s.Pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT set_config('app.customer_id', $1, true)", customerID); err != nil {
			return err
		}
		return fn(tx)
	})
}

// WithStaff runs fn in a transaction scoped to a staff role ("agent" or "supervisor").
func (s *Store) WithStaff(ctx context.Context, role string, fn func(pgx.Tx) error) error {
	if role != "agent" && role != "supervisor" {
		return errors.New("invalid staff role")
	}
	return pgx.BeginFunc(ctx, s.Pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT set_config('app.staff_role', $1, true)", role); err != nil {
			return err
		}
		return fn(tx)
	})
}
