package orchestrator

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
)

// analyticsRanges maps the accepted ?range= values to their length and chart granularity. "all" has no start.
var analyticsRanges = map[string]struct {
	span   time.Duration
	bucket string
}{
	"24h": {24 * time.Hour, "hour"},
	"7d":  {7 * 24 * time.Hour, "day"},
	"30d": {30 * 24 * time.Hour, "day"},
	"all": {0, "day"},
}

// ParseRange validates ?range= ("" means 24h) and returns the start (nil for "all") and the bucket size.
func ParseRange(r string, now time.Time) (string, *time.Time, string, bool) {
	if r == "" {
		r = "24h"
	}
	spec, ok := analyticsRanges[r]
	if !ok {
		return "", nil, "", false
	}
	if spec.span == 0 {
		return r, nil, spec.bucket, true
	}
	from := now.Add(-spec.span)
	return r, &from, spec.bucket, true
}

// Analytics aggregates the audit trail and the handoff queue for the supervisor's "Resumen". Staff RLS lets this
// read only audit_events and handoffs, which is exactly what it needs.
func (o *Orchestrator) Analytics(ctx context.Context, p auth.Principal, rangeParam string) (contract.Analytics, error) {
	name, from, bucket, ok := ParseRange(rangeParam, time.Now())
	if !ok {
		return contract.Analytics{}, ErrBadRequest
	}
	a := contract.Analytics{Range: name, From: from, Bucket: bucket, Series: []contract.SeriesPoint{},
		ByMode: []contract.ModeOutcome{}, ByLang: []contract.LabelCount{}, TopRules: []contract.LabelCount{},
		Handoffs: []contract.ReasonCount{}, Funnel: []contract.FunnelStep{}, StepLatency: []contract.StepLatency{}}
	since := time.Time{} // "all": the zero time is before every row
	if from != nil {
		since = *from
	}
	err := o.Store.WithStaff(ctx, p.StaffRole(), p.Username, func(tx pgx.Tx) error {
		k := &a.KPIs
		if err := tx.QueryRow(ctx, `SELECT
			  count(DISTINCT session_id) FILTER (WHERE mode = 'system'),
			  count(*) FILTER (WHERE step = 'respond' AND mode = 'system'),
			  count(*) FILTER (WHERE step = 'act' AND tool = 'open_dispute_case' AND result = 'executed'),
			  count(*) FILTER (WHERE step = 'act' AND tool = 'block_card' AND result = 'executed'),
			  count(*) FILTER (WHERE step = 'policy' AND mode = 'system' AND policy_rule_id LIKE 'EXPLAIN-%'),
			  count(*) FILTER (WHERE step = 'respond' AND mode = 'system' AND result = 'escalate'),
			  count(*) FILTER (WHERE step = 'respond' AND mode = 'system' AND policy_rule_id = 'SEC-INJ-01'),
			  count(*) FILTER (WHERE step = 'respond' AND mode = 'system' AND policy_rule_id = 'ESC-TECH-01'),
			  coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE step = 'respond' AND mode = 'system'), 0),
			  coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE step = 'respond' AND mode = 'system'), 0),
			  count(*) FILTER (WHERE step = 'notify' AND tool = 'send_email' AND result = 'sent'),
			  count(*) FILTER (WHERE step = 'notify' AND tool = 'send_email' AND result = 'failed')
			FROM audit_events WHERE ts >= $1`, since).Scan(&k.Conversations, &k.Turns, &k.CasesOpened, &k.CardsBlocked,
			&k.Explained, &k.Escalated, &k.InjectionsBlocked, &k.TechFailures, &k.P50LatencyMS, &k.P95LatencyMS,
			&k.EmailsSent, &k.EmailsFailed); err != nil {
			return err
		}
		if err := tx.QueryRow(ctx, `SELECT
			  (SELECT count(*) FROM handoffs WHERE status = 'open'),
			  count(*) FILTER (WHERE status = 'claimed'),
			  count(*) FILTER (WHERE status = 'closed'),
			  coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM claimed_at - created_at))
			           FILTER (WHERE claimed_at IS NOT NULL), 0),
			  count(*) FILTER (WHERE payload->'resolution'->>'outcome' = 'accepted'),
			  count(*) FILTER (WHERE payload->'resolution'->>'outcome' = 'rejected')
			FROM handoffs WHERE created_at >= $1`, since).Scan(&k.HandoffsOpen, &k.HandoffsClaimed, &k.HandoffsClosed,
			&k.MedianClaimSeconds, &k.Accepted, &k.Rejected); err != nil {
			return err
		}

		var err error
		if a.Series, err = collect(ctx, tx, `SELECT date_trunc($2, ts), coalesce(mode, ''), coalesce(result, ''), count(*)
			FROM audit_events WHERE step = 'respond' AND ts >= $1 GROUP BY 1, 2, 3 ORDER BY 1`,
			func(r pgx.CollectableRow) (contract.SeriesPoint, error) {
				var s contract.SeriesPoint
				return s, r.Scan(&s.Bucket, &s.Mode, &s.Outcome, &s.Count)
			}, since, bucket); err != nil {
			return err
		}
		if a.ByMode, err = collect(ctx, tx, `SELECT coalesce(mode, ''), coalesce(result, ''), count(*)
			FROM audit_events WHERE step = 'respond' AND ts >= $1 GROUP BY 1, 2 ORDER BY 1, 3 DESC`,
			func(r pgx.CollectableRow) (contract.ModeOutcome, error) {
				var m contract.ModeOutcome
				return m, r.Scan(&m.Mode, &m.Outcome, &m.Count)
			}, since); err != nil {
			return err
		}
		labelCount := func(r pgx.CollectableRow) (contract.LabelCount, error) {
			var l contract.LabelCount
			return l, r.Scan(&l.Label, &l.Count)
		}
		if a.ByLang, err = collect(ctx, tx, `SELECT coalesce(lang, ''), count(DISTINCT session_id)
			FROM audit_events WHERE mode = 'system' AND ts >= $1 GROUP BY 1 ORDER BY 2 DESC`, labelCount, since); err != nil {
			return err
		}
		if a.TopRules, err = collect(ctx, tx, `SELECT policy_rule_id, count(*) FROM audit_events
			WHERE step = 'respond' AND mode = 'system' AND coalesce(policy_rule_id, '') <> '' AND ts >= $1
			GROUP BY 1 ORDER BY 2 DESC LIMIT 10`, labelCount, since); err != nil {
			return err
		}
		if a.Handoffs, err = collect(ctx, tx, `SELECT reason, priority, count(*) FROM handoffs
			WHERE created_at >= $1 GROUP BY 1, 2 ORDER BY 3 DESC`,
			func(r pgx.CollectableRow) (contract.ReasonCount, error) {
				var c contract.ReasonCount
				return c, r.Scan(&c.Reason, &c.Priority, &c.Count)
			}, since); err != nil {
			return err
		}
		// How far conversations get: understood -> transaction found -> action proposed -> confirmed -> verified.
		if a.Funnel, err = collect(ctx, tx, `SELECT stage, count(DISTINCT session_id) FROM (
			  SELECT session_id, CASE
			    WHEN step = 'understand' THEN '1_understood'
			    WHEN step = 'find_transactions' AND result <> '0' THEN '2_found'
			    WHEN step = 'propose' THEN '3_proposed'
			    WHEN step = 'confirm' AND result = 'confirmed' THEN '4_confirmed'
			    WHEN step = 'verify' AND result = 'verified' THEN '5_verified'
			  END AS stage
			  FROM audit_events WHERE mode = 'system' AND ts >= $1) s
			WHERE stage IS NOT NULL GROUP BY 1 ORDER BY 1`,
			func(r pgx.CollectableRow) (contract.FunnelStep, error) {
				var f contract.FunnelStep
				err := r.Scan(&f.Step, &f.Sessions)
				if len(f.Step) > 2 {
					f.Step = f.Step[2:] // drop the ordering prefix
				}
				return f, err
			}, since); err != nil {
			return err
		}
		a.StepLatency, err = collect(ctx, tx, `SELECT step, avg(latency_ms)::float8,
			  percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), count(*)
			FROM audit_events WHERE mode = 'system' AND latency_ms > 0 AND ts >= $1
			GROUP BY 1 ORDER BY 2 DESC`,
			func(r pgx.CollectableRow) (contract.StepLatency, error) {
				var s contract.StepLatency
				return s, r.Scan(&s.Step, &s.AvgMS, &s.P95MS, &s.Count)
			}, since)
		return err
	})
	return a, err
}

func collect[T any](ctx context.Context, tx pgx.Tx, sql string, scan pgx.RowToFunc[T], args ...any) ([]T, error) {
	rows, err := tx.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	out, err := pgx.CollectRows(rows, scan)
	if out == nil {
		out = []T{}
	}
	return out, err
}
