package orchestrator

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/tools"
)

// Overview returns the customer's own cards and latest card movements (RLS-scoped).
func (o *Orchestrator) Overview(ctx context.Context, p auth.Principal) (contract.Overview, error) {
	v := contract.Overview{Cards: []contract.Card{}, Recent: []contract.Candidate{}, Today: o.Today.Format("2006-01-02")}
	err := o.Store.WithCustomer(ctx, p.CustomerRef, func(tx pgx.Tx) error {
		v.FirstName, _, _ = o.customerNames(ctx, tx)
		cards, err := tools.ActiveCards(ctx, tx)
		if err != nil {
			return err
		}
		for _, c := range cards {
			v.Cards = append(v.Cards, contract.Card{Last4: c.Last4, Type: c.Type, Status: c.Status})
		}
		recent, err := tools.FindTransactions(ctx, tx, tools.Filter{From: o.Today.AddDate(0, -6, 0), To: o.Today,
			Types: []string{"Purchase", "Withdrawal"}}, 8)
		if err != nil {
			return err
		}
		for _, t := range recent {
			v.Recent = append(v.Recent, contract.Candidate{TransactionID: t.ID, Date: t.Date, Amount: t.Amount,
				Currency: t.Currency, Merchant: t.Merchant, City: t.City, Country: t.Country, CardLast4: t.CardLast4})
		}
		return nil
	})
	return v, err
}

// Session returns the customer's own conversation (used to restore the chat after a step-up redirect).
func (o *Orchestrator) Session(ctx context.Context, p auth.Principal, id string) (contract.SessionView, error) {
	var v contract.SessionView
	err := o.Store.WithCustomer(ctx, p.CustomerRef, func(tx pgx.Tx) error {
		var raw []byte
		err := tx.QueryRow(ctx, `SELECT session_id, lang, state FROM chat_sessions WHERE session_id = $1`, id).Scan(&v.SessionID, &v.Lang, &raw)
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrNotFound
		} else if err != nil {
			return err
		}
		var st state
		_ = json.Unmarshal(raw, &st)
		rows, err := tx.Query(ctx, `SELECT role, text, created_at FROM messages WHERE session_id = $1 ORDER BY id`, id)
		if err != nil {
			return err
		}
		v.Messages, err = pgx.CollectRows(rows, func(r pgx.CollectableRow) (contract.Message, error) {
			var m contract.Message
			return m, r.Scan(&m.Role, &m.Text, &m.At)
		})
		if err != nil {
			return err
		}
		if st.Stage == stageAwaitingConfirm && st.PendingAction != "" {
			var actionType string
			if tx.QueryRow(ctx, `SELECT action_type FROM pending_actions WHERE action_id = $1 AND status = 'pending'`,
				st.PendingAction).Scan(&actionType) == nil {
				summary := ""
				if n := len(v.Messages); n > 0 {
					summary = v.Messages[n-1].Text
				}
				v.PendingAction = &contract.PendingAction{ID: st.PendingAction, Type: actionType, Summary: summary,
					RequiresStepUp: o.Policy.RequiresStepUp(actionType)}
			}
		}
		return nil
	})
	return v, err
}

func (o *Orchestrator) ListHandoffs(ctx context.Context, p auth.Principal, status string) ([]contract.HandoffSummary, error) {
	out := []contract.HandoffSummary{}
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT handoff_id, created_at, status, language, reason, priority,
			payload->>'suggested_queue', coalesce(payload->>'dispute_type', ''), claimed_by, claimed_at
			FROM handoffs WHERE ($1 = '' OR status = $1)
			-- Open: most urgent first, then whoever has waited longest. Claimed: most recently taken first.
			ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
			         CASE WHEN status = 'open' THEN created_at END ASC,
			         claimed_at DESC NULLS LAST, created_at DESC
			LIMIT 100`, status)
		if err != nil {
			return err
		}
		out, err = pgx.CollectRows(rows, func(r pgx.CollectableRow) (contract.HandoffSummary, error) {
			var h contract.HandoffSummary
			return h, r.Scan(&h.HandoffID, &h.CreatedAt, &h.Status, &h.Language, &h.Reason, &h.Priority, &h.Queue, &h.DisputeType, &h.ClaimedBy, &h.ClaimedAt)
		})
		return err
	})
	return out, err
}

func (o *Orchestrator) GetHandoff(ctx context.Context, p auth.Principal, id string) (contract.Handoff, error) {
	var h contract.Handoff
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error { return loadHandoff(ctx, tx, id, &h) })
	return h, err
}

// ClaimHandoff assigns an open handoff to the calling agent.
func (o *Orchestrator) ClaimHandoff(ctx context.Context, p auth.Principal, id string) (contract.Handoff, error) {
	var h contract.Handoff
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		tag, err := tx.Exec(ctx, `UPDATE handoffs SET status = 'claimed', claimed_by = $2, claimed_at = now()
			WHERE handoff_id = $1 AND status = 'open'`, id, p.Username)
		if err != nil {
			return err
		}
		if tag.RowsAffected() == 0 {
			return ErrNotFound
		}
		return loadHandoff(ctx, tx, id, &h)
	})
	return h, err
}

const maxResolutionNote = 1000

// CloseHandoff closes a handoff the calling agent has claimed, recording the outcome in the payload and in the
// customer's audit trail (the note itself stays out of the audit summary, which must not carry free text).
func (o *Orchestrator) CloseHandoff(ctx context.Context, p auth.Principal, id string, req contract.CloseRequest) (contract.Handoff, error) {
	note := strings.TrimSpace(req.Note)
	if (req.Outcome != "accepted" && req.Outcome != "rejected") || note == "" || utf8.RuneCountInString(note) > maxResolutionNote {
		return contract.Handoff{}, ErrBadRequest
	}
	var h contract.Handoff
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		tag, err := tx.Exec(ctx, `UPDATE handoffs SET status = 'closed', payload = payload || jsonb_build_object('resolution',
			jsonb_build_object('outcome', $3::text, 'note', $4::text, 'closed_by', $2::text, 'closed_at', now()))
			WHERE handoff_id = $1 AND status = 'claimed' AND claimed_by = $2`, id, p.Username, req.Outcome, note)
		if err != nil {
			return err
		}
		if tag.RowsAffected() == 0 {
			return ErrNotFound // not found, not claimed, or claimed by someone else
		}
		if _, err := tx.Exec(ctx, `INSERT INTO audit_events (session_id, customer_id, step, tool, summary, result)
			SELECT session_id, customer_id, 'handoff', 'close_handoff', 'handoff closed by ' || $2::text, $3::text
			FROM handoffs WHERE handoff_id = $1`, id, p.Username, req.Outcome); err != nil {
			return err
		}
		return loadHandoff(ctx, tx, id, &h)
	})
	return h, err
}

// MyDisputes lists the customer's own dispute cases and specialist handoffs, newest first (RLS-scoped).
func (o *Orchestrator) MyDisputes(ctx context.Context, p auth.Principal) ([]contract.MyDispute, error) {
	out := []contract.MyDispute{}
	err := o.Store.WithCustomer(ctx, p.CustomerRef, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `
			SELECT 'case', c.case_id, c.dispute_type, c.status, c.created_at, coalesce(t.merchant_name, ''), t.amount::float8,
			       t.currency, t.transaction_date, coalesce(p.card_last4, ''), NULL::jsonb
			FROM dispute_cases c JOIN transactions t USING (transaction_id) JOIN products p ON p.product_id = t.product_id
			UNION ALL
			SELECT 'handoff', h.handoff_id::text, coalesce(h.payload->>'dispute_type', ''), h.status, h.created_at, '',
			       NULL::float8, '', NULL::timestamptz, '', h.payload->'resolution'
			FROM handoffs h WHERE h.reason <> 'baseline_human_review'
			ORDER BY 5 DESC LIMIT 50`)
		if err != nil {
			return err
		}
		out, err = pgx.CollectRows(rows, func(r pgx.CollectableRow) (contract.MyDispute, error) {
			var d contract.MyDispute
			var currency *string
			var resolution []byte
			if err := r.Scan(&d.Kind, &d.ID, &d.DisputeType, &d.Status, &d.CreatedAt, &d.Merchant, &d.Amount, &currency,
				&d.TxnDate, &d.CardLast4, &resolution); err != nil {
				return d, err
			}
			if currency != nil {
				d.Currency = *currency
			}
			if len(resolution) > 0 {
				d.Resolution = &contract.Resolution{}
				if err := json.Unmarshal(resolution, d.Resolution); err != nil {
					return d, err
				}
			}
			return d, nil
		})
		return err
	})
	return out, err
}

func loadHandoff(ctx context.Context, tx pgx.Tx, id string, h *contract.Handoff) error {
	var raw []byte
	var status string
	var claimedBy *string
	err := tx.QueryRow(ctx, `SELECT payload, status, claimed_by, handoff_id, created_at FROM handoffs WHERE handoff_id = $1`, id).
		Scan(&raw, &status, &claimedBy, &h.HandoffID, &h.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrNotFound
	} else if err != nil {
		return err
	}
	createdAt, handoffID := h.CreatedAt, h.HandoffID
	if err := json.Unmarshal(raw, h); err != nil {
		return err
	}
	h.HandoffID, h.CreatedAt, h.Status, h.ClaimedBy = handoffID, createdAt, status, claimedBy
	return nil
}

func (o *Orchestrator) SessionAudit(ctx context.Context, p auth.Principal, sessionID string) ([]contract.AuditEvent, error) {
	out := []contract.AuditEvent{}
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT ts, step, tool, summary, result, policy_rule_id, trace_id, coalesce(latency_ms, 0)
			FROM audit_events WHERE session_id = $1 ORDER BY id`, sessionID)
		if err != nil {
			return err
		}
		out, err = pgx.CollectRows(rows, func(r pgx.CollectableRow) (contract.AuditEvent, error) {
			var e contract.AuditEvent
			return e, r.Scan(&e.TS, &e.Step, &e.Tool, &e.Summary, &e.Result, &e.RuleID, &e.TraceID, &e.LatencyMS)
		})
		return err
	})
	return out, err
}

// Summary aggregates completed turns from the audit trail (staff-visible, no personal data).
func (o *Orchestrator) Summary(ctx context.Context, p auth.Principal) (contract.Summary, error) {
	s := contract.Summary{ByOutcome: []contract.OutcomeCount{}}
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `SELECT count(*), coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0),
			coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)
			FROM audit_events WHERE step = 'respond'`).Scan(&s.Turns, &s.P50LatencyMS, &s.P95LatencyMS); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT coalesce(result, ''), coalesce(lang, ''), coalesce(mode, ''), count(*)
			FROM audit_events WHERE step = 'respond' GROUP BY 1, 2, 3 ORDER BY 4 DESC`)
		if err != nil {
			return err
		}
		s.ByOutcome, err = pgx.CollectRows(rows, func(r pgx.CollectableRow) (contract.OutcomeCount, error) {
			var c contract.OutcomeCount
			return c, r.Scan(&c.Outcome, &c.Lang, &c.Mode, &c.Count)
		})
		if err != nil {
			return err
		}
		return tx.QueryRow(ctx, `SELECT count(*) FROM handoffs WHERE status = 'open'`).Scan(&s.OpenHandoffs)
	})
	return s, err
}
