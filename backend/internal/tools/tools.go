// Package tools implements the simulated bank tools. Every write is verified by reading it back; callers
// report an action to the customer only when Verified is true.
//
// Pipeline role: Decide (FindTransactions, FindDuplicates, GetTransaction, ConvertUSD read the customer's own
// records) and Act + Verify (OpenDisputeCase, BlockCard write and read back). All run inside the turn's
// customer-scoped transaction, so row-level security limits them to the caller's rows. No tool moves money.
package tools

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/factored-hackathon-2026/disputes/backend/internal/textnorm"
)

// Transaction is a card transaction joined with its card's last four digits and brand.
type Transaction struct {
	ID        string    `json:"transaction_id"`
	ProductID string    `json:"-"`
	Date      time.Time `json:"date"`
	Type      string    `json:"-"`
	Amount    float64   `json:"amount"`
	Currency  string    `json:"currency"`
	AmountUSD *float64  `json:"-"`
	Merchant  string    `json:"merchant"`
	City      string    `json:"city"`
	Country   string    `json:"country"`
	Status    string    `json:"-"`
	CardLast4 string    `json:"card_last4"`
	CardBrand string    `json:"card_brand"`
}

// Filter narrows FindTransactions: a date window plus optional amount and merchant hint.
type Filter struct {
	From, To     time.Time
	Amount       *float64
	MerchantHint string
	Types        []string // transaction types, e.g. Purchase, Withdrawal
}

const txnColumns = `t.transaction_id, t.product_id, t.transaction_date, t.transaction_type, t.amount::float8,
	t.currency, t.amount_usd::float8, coalesce(t.merchant_name, ''), coalesce(t.transaction_city, ''),
	coalesce(t.transaction_country, ''), t.transaction_status, coalesce(p.card_last4, ''), coalesce(p.card_brand, '')`

// scanTxn reads one row selected with txnColumns.
func scanTxn(row pgx.Row) (Transaction, error) {
	var t Transaction
	err := row.Scan(&t.ID, &t.ProductID, &t.Date, &t.Type, &t.Amount, &t.Currency, &t.AmountUSD,
		&t.Merchant, &t.City, &t.Country, &t.Status, &t.CardLast4, &t.CardBrand)
	return t, err
}

// FindTransactions returns the customer's card transactions matching the filter (RLS scopes the customer).
func FindTransactions(ctx context.Context, tx pgx.Tx, f Filter, limit int) ([]Transaction, error) {
	rows, err := tx.Query(ctx, `SELECT `+txnColumns+`
		FROM transactions t JOIN products p USING (product_id)
		WHERE p.product_type IN ('Credit Card', 'Debit Card') AND t.transaction_date BETWEEN $1 AND $2
		  AND t.transaction_type = ANY($3)
		ORDER BY t.transaction_date DESC LIMIT 200`, f.From, f.To, f.Types)
	if err != nil {
		return nil, err
	}
	all, err := pgx.CollectRows(rows, func(r pgx.CollectableRow) (Transaction, error) { return scanTxn(r) })
	if err != nil {
		return nil, err
	}
	var out []Transaction
	hint := textnorm.Normalize(f.MerchantHint)
	for _, t := range all {
		if f.Amount != nil && math.Abs(t.Amount-*f.Amount) > math.Max(1, *f.Amount*0.02) {
			continue
		}
		if hint != "" && !strings.Contains(textnorm.Normalize(t.Merchant), hint) {
			continue
		}
		out = append(out, t)
		if len(out) == limit {
			break
		}
	}
	return out, nil
}

// FindDuplicates returns the later transaction of each same-merchant, same-amount pair within 2 days.
func FindDuplicates(ctx context.Context, tx pgx.Tx, from, to time.Time, limit int) ([]Transaction, error) {
	rows, err := tx.Query(ctx, `SELECT `+txnColumns+`
		FROM transactions t JOIN products p USING (product_id)
		WHERE p.product_type IN ('Credit Card', 'Debit Card') AND t.transaction_date BETWEEN $1 AND $2
		  AND EXISTS (SELECT 1 FROM transactions o
		              WHERE o.product_id = t.product_id AND o.transaction_id <> t.transaction_id
		                AND o.amount = t.amount AND o.merchant_name = t.merchant_name
		                AND o.transaction_date < t.transaction_date
		                AND o.transaction_date >= t.transaction_date - interval '2 days')
		ORDER BY t.transaction_date DESC LIMIT $3`, from, to, limit)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Transaction, error) { return scanTxn(r) })
}

// GetTransaction reads one transaction by id; RLS returns no rows for another customer's transaction.
func GetTransaction(ctx context.Context, tx pgx.Tx, id string) (Transaction, error) {
	return scanTxn(tx.QueryRow(ctx, `SELECT `+txnColumns+`
		FROM transactions t JOIN products p USING (product_id) WHERE t.transaction_id = $1`, id))
}

// Conversion is a transaction amount in USD at the exchange rate of its date (ADR 0002).
type Conversion struct {
	USD      float64
	Rate     float64   // USD per unit of the transaction currency; 0 when only the dataset's amount_usd was available
	RateDate time.Time // the rate's date (the last one on or before the transaction date)
}

// ConvertUSD converts with the exchange rate of the transaction date; falls back to the last prior rate, then to
// the dataset's own amount_usd (no rate to show).
func ConvertUSD(ctx context.Context, tx pgx.Tx, t Transaction) (Conversion, error) {
	if t.Currency == "USD" {
		return Conversion{USD: t.Amount, Rate: 1, RateDate: t.Date}, nil
	}
	var c Conversion
	err := tx.QueryRow(ctx, `SELECT exchange_rate::float8, rate_date FROM exchange_rates
		WHERE source_currency = $1 AND target_currency = 'USD' AND rate_date <= $2::date
		ORDER BY rate_date DESC LIMIT 1`, t.Currency, t.Date).Scan(&c.Rate, &c.RateDate)
	if err != nil {
		if t.AmountUSD != nil {
			return Conversion{USD: *t.AmountUSD}, nil
		}
		return Conversion{}, fmt.Errorf("no %s->USD rate for %s", t.Currency, t.Date.Format(time.DateOnly))
	}
	c.USD = math.Round(t.Amount*c.Rate*100) / 100
	return c, nil
}

// AmountUSD is ConvertUSD plus a one-line description of the rate used, for the audit trail.
func AmountUSD(ctx context.Context, tx pgx.Tx, t Transaction) (float64, string, error) {
	c, err := ConvertUSD(ctx, tx, t)
	switch {
	case err != nil:
		return 0, "", err
	case t.Currency == "USD":
		return c.USD, "USD 1.0", nil
	case c.Rate == 0:
		return c.USD, "dataset amount_usd", nil
	}
	return c.USD, fmt.Sprintf("%s->USD %.6f (%s)", t.Currency, c.Rate, c.RateDate.Format(time.DateOnly)), nil
}

// Card is one of the customer's credit or debit cards.
type Card struct {
	ProductID string
	Last4     string
	Brand     string
	Status    string
	Type      string
}

// ActiveCards lists the customer's cards, active first.
func ActiveCards(ctx context.Context, tx pgx.Tx) ([]Card, error) {
	rows, err := tx.Query(ctx, `SELECT product_id, coalesce(card_last4, ''), coalesce(card_brand, ''), product_status, product_type
		FROM products WHERE product_type IN ('Credit Card', 'Debit Card') ORDER BY (product_status = 'Active') DESC, product_id`)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Card, error) {
		var c Card
		return c, r.Scan(&c.ProductID, &c.Last4, &c.Brand, &c.Status, &c.Type)
	})
}

// Verified is the proof of an executed action: the reference read back from the database and when it was written.
type Verified struct {
	Reference  string
	VerifiedAt time.Time
}

// ErrNotVerified means a write could not be confirmed by reading it back; the orchestrator then escalates.
var ErrNotVerified = errors.New("action could not be verified")

// OpenDisputeCase inserts the case (idempotent on key) and verifies it by reading it back.
func OpenDisputeCase(ctx context.Context, tx pgx.Tx, txnID, disputeType, description, idempotencyKey string) (Verified, error) {
	_, err := tx.Exec(ctx, `INSERT INTO dispute_cases (transaction_id, dispute_type, description, idempotency_key)
		VALUES ($1, $2, $3, $4) ON CONFLICT (idempotency_key) DO NOTHING`,
		txnID, disputeType, description, idempotencyKey)
	if err != nil {
		return Verified{}, err
	}
	var v Verified
	var gotTxn, status string
	err = tx.QueryRow(ctx, `SELECT case_id, transaction_id, status, created_at FROM dispute_cases WHERE idempotency_key = $1`,
		idempotencyKey).Scan(&v.Reference, &gotTxn, &status, &v.VerifiedAt)
	if err != nil || gotTxn != txnID || status != "open" {
		return Verified{}, ErrNotVerified
	}
	return v, nil
}

// OpenCaseFor returns the open dispute case for a transaction, if any.
func OpenCaseFor(ctx context.Context, tx pgx.Tx, txnID string) (string, bool, error) {
	var id string
	err := tx.QueryRow(ctx, `SELECT case_id FROM dispute_cases WHERE transaction_id = $1 AND status = 'open' LIMIT 1`, txnID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	return id, err == nil, err
}

// BlockCard sets the card to Blocked and verifies the new status by reading it back.
func BlockCard(ctx context.Context, tx pgx.Tx, productID, reason string) (Verified, error) {
	tag, err := tx.Exec(ctx, `UPDATE products SET product_status = 'Blocked' WHERE product_id = $1`, productID)
	if err != nil {
		return Verified{}, err
	}
	if tag.RowsAffected() != 1 {
		return Verified{}, ErrNotVerified
	}
	var v Verified
	if err := tx.QueryRow(ctx, `INSERT INTO card_blocks (product_id, reason) VALUES ($1, $2)
		RETURNING block_id, created_at`, productID, reason).Scan(&v.Reference, &v.VerifiedAt); err != nil {
		return Verified{}, err
	}
	var status string
	if err := tx.QueryRow(ctx, `SELECT product_status FROM products WHERE product_id = $1`, productID).Scan(&status); err != nil || status != "Blocked" {
		return Verified{}, ErrNotVerified
	}
	return v, nil
}

// Agent is a service agent suggested in a handoff (name, languages, specialty).
type Agent struct {
	AgentID   string `json:"agent_id"`
	Name      string `json:"name"`
	Languages string `json:"languages"`
	Specialty string `json:"specialty"`
}

// SuggestAgents finds active agents who speak the customer's language, preferring the queue's specialty.
func SuggestAgents(ctx context.Context, tx pgx.Tx, lang, queue string) ([]Agent, error) {
	language := map[string]string{"es": "español", "pt": "portugués"}[lang]
	specialty := map[string]string{"fraud": "Fraudes", "disputes": "Quejas y Reclamos"}[queue]
	rows, err := tx.Query(ctx, `SELECT agent_id, first_name || ' ' || last_name, languages, coalesce(specialty, '')
		FROM service_agents WHERE agent_status = 'Active' AND languages LIKE '%' || $1 || '%'
		ORDER BY (specialty IS NOT DISTINCT FROM $2) DESC, agent_id LIMIT 3`, language, specialty)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(r pgx.CollectableRow) (Agent, error) {
		var a Agent
		return a, r.Scan(&a.AgentID, &a.Name, &a.Languages, &a.Specialty)
	})
}
