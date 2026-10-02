package orchestrator

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/prometheus/client_golang/prometheus"
)

// queueCollector exposes the specialists' handoff queue to Prometheus. It reads Postgres on every scrape (one
// small aggregate per 10-15 s) as the supervisor role, so it sees exactly what the supervisor view sees: counts,
// never customer data.
type queueCollector struct {
	o                       *Orchestrator
	open, oldest, byOutcome *prometheus.Desc
}

// QueueCollector is registered once in main: prometheus.MustRegister(orch.QueueCollector()).
func (o *Orchestrator) QueueCollector() prometheus.Collector {
	return &queueCollector{o: o,
		open: prometheus.NewDesc("handoffs_open", "Handoffs waiting for a specialist, by priority.", []string{"priority"}, nil),
		oldest: prometheus.NewDesc("handoffs_oldest_wait_seconds",
			"How long the oldest open handoff has been waiting (0 when the queue is empty).", nil, nil),
		byOutcome: prometheus.NewDesc("handoffs_by_status",
			"Handoffs ever created, by current status and, once closed, the specialist's resolution.", []string{"status", "resolution"}, nil),
	}
}

func (c *queueCollector) Describe(ch chan<- *prometheus.Desc) {
	ch <- c.open
	ch <- c.oldest
	ch <- c.byOutcome
}

func (c *queueCollector) Collect(ch chan<- prometheus.Metric) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	open := map[string]float64{"high": 0, "medium": 0}
	var oldest float64
	type key struct{ status, resolution string }
	totals := map[key]float64{}
	err := c.o.Store.WithStaff(ctx, "supervisor", "metrics", func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT priority, count(*) FROM handoffs WHERE status = 'open' GROUP BY 1`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var p string
			var n float64
			if err := rows.Scan(&p, &n); err != nil {
				return err
			}
			open[p] = n
		}
		if err := rows.Err(); err != nil {
			return err
		}
		if err := tx.QueryRow(ctx, `SELECT coalesce(extract(epoch FROM now() - min(created_at)), 0)::float8
			FROM handoffs WHERE status = 'open'`).Scan(&oldest); err != nil {
			return err
		}
		rows, err = tx.Query(ctx, `SELECT status, coalesce(payload->'resolution'->>'outcome', ''), count(*)
			FROM handoffs GROUP BY 1, 2`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var k key
			var n float64
			if err := rows.Scan(&k.status, &k.resolution, &n); err != nil {
				return err
			}
			totals[k] = n
		}
		return rows.Err()
	})
	if err != nil {
		// No sample at all is better than a wrong zero: Prometheus then shows a gap, and the error is logged.
		slog.Warn("queue metrics unavailable", "err", err)
		return
	}
	for p, n := range open {
		ch <- prometheus.MustNewConstMetric(c.open, prometheus.GaugeValue, n, p)
	}
	ch <- prometheus.MustNewConstMetric(c.oldest, prometheus.GaugeValue, oldest)
	for k, n := range totals {
		ch <- prometheus.MustNewConstMetric(c.byOutcome, prometheus.GaugeValue, n, k.status, k.resolution)
	}
}
