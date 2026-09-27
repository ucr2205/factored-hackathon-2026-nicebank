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

// Write records an event for the customer pinned in the transaction (the column default).
func Write(ctx context.Context, tx pgx.Tx, e Event) error {
	_, err := tx.Exec(ctx, `INSERT INTO audit_events
		(session_id, step, tool, summary, result, policy_rule_id, trace_id, latency_ms, lang, mode)
		VALUES ($1, $2, NULLIF($3, ''), $4, NULLIF($5, ''), NULLIF($6, ''), NULLIF($7, ''), $8, NULLIF($9, ''), NULLIF($10, ''))`,
		nullUUID(e.SessionID), e.Step, e.Tool, e.Summary, e.Result, e.RuleID, e.TraceID,
		int(e.Latency.Milliseconds()), e.Lang, e.Mode)
	return err
}

func nullUUID(s string) any {
	if s == "" {
		return nil
	}
	return s
}
