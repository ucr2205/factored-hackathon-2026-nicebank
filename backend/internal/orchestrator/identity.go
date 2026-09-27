package orchestrator

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
)

// customerNames decrypts the pinned customer's names in memory (RLS returns only that customer's row).
// Callers use them for the greeting and to mask names before text reaches a model; they are never stored,
// logged or traced.
func (o *Orchestrator) customerNames(ctx context.Context, tx pgx.Tx) (first, last string, err error) {
	if o.PII == nil {
		return "", "", errors.New("pii cipher not configured")
	}
	var id string
	var firstCT, lastCT []byte
	var version int
	if err := tx.QueryRow(ctx, `SELECT customer_id, first_name_ct, last_name_ct, key_version FROM customer_identity`).
		Scan(&id, &firstCT, &lastCT, &version); err != nil {
		return "", "", err
	}
	if first, err = o.PII.Decrypt(id, "first_name", version, firstCT); err != nil {
		return "", "", err
	}
	last, err = o.PII.Decrypt(id, "last_name", version, lastCT)
	return first, last, err
}

// RevealIdentity returns the customer's identity for a handoff the calling agent has claimed. The database
// function checks the claim and writes the audit event; anything else gets ErrNotFound.
func (o *Orchestrator) RevealIdentity(ctx context.Context, p auth.Principal, handoffID string) (contract.CustomerIdentity, error) {
	var out contract.CustomerIdentity
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		var id string
		var firstCT, lastCT []byte
		var version int
		err := tx.QueryRow(ctx, `SELECT customer_id, customer_ref, first_name_ct, last_name_ct, key_version
			FROM reveal_customer_identity($1)`, handoffID).Scan(&id, &out.CustomerRef, &firstCT, &lastCT, &version)
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrNotFound
		} else if err != nil {
			return err
		}
		if out.FirstName, err = o.PII.Decrypt(id, "first_name", version, firstCT); err != nil {
			return err
		}
		out.LastName, err = o.PII.Decrypt(id, "last_name", version, lastCT)
		return err
	})
	return out, err
}
