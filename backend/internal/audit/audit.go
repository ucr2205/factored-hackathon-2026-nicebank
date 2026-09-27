// Package audit writes execution records. These rows — not model reasoning — are the audit evidence:
// which step ran, which tool, what it returned and which policy rule justified it.
package audit

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"
)

type Event struct {
	SessionID string
	Step      string // understand | extract | find_transactions | policy | propose | confirm | act | verify | handoff | respond
	Tool      string
	Summary   string // no personal data: ids, types, amounts, rule ids
	Result    string
	RuleID    string
	TraceID   string
	Latency   time.Duration
	Lang      string
	Mode      string
}

func Write(ctx context.Context, tx pgx.Tx, customerID string, e Event) error {
	_, err := tx.Exec(ctx, `INSERT INTO audit_events
		(session_id, customer_id, step, tool, summary, result, policy_rule_id, trace_id, latency_ms, lang, mode)
		VALUES ($1, $2, $3, NULLIF($4, ''), $5, NULLIF($6, ''), NULLIF($7, ''), NULLIF($8, ''), $9, NULLIF($10, ''), NULLIF($11, ''))`,
		nullUUID(e.SessionID), customerID, e.Step, e.Tool, e.Summary, e.Result, e.RuleID, e.TraceID,
		int(e.Latency.Milliseconds()), e.Lang, e.Mode)
	return err
}

func nullUUID(s string) any {
	if s == "" {
		return nil
	}
	return s
}
