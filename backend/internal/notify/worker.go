package notify

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"

	"github.com/factored-hackathon-2026/disputes/backend/internal/pii"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
)

// Worker delivers pending notifications from the outbox. It is safe to run in several backend instances:
// claim_notifications() uses FOR UPDATE SKIP LOCKED and a 5-minute lease.
type Worker struct {
	Pool        *pgxpool.Pool
	PII         *pii.Cipher
	Mailer      Mailer
	Interval    time.Duration // polling period
	Batch       int
	MaxAttempts int
	AppURL      string // customer app, used as the email's call-to-action link
	Concurrency int    // parallel SMTP sends per batch (default 1)
}

func (w *Worker) Run(ctx context.Context) {
	t := time.NewTicker(w.Interval)
	defer t.Stop()
	for {
		if _, err := w.RunOnce(ctx); err != nil && ctx.Err() == nil {
			slog.Warn("notifier: claim failed", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
	}
}

type claimed struct {
	ID          int64
	CustomerID  string
	Kind, Lang  string
	Payload     []byte
	Attempts    int
	EmailCT     []byte
	FirstNameCT []byte
	KeyVersion  *int
}

// RunOnce claims and processes one batch; it returns how many notifications it handled.
func (w *Worker) RunOnce(ctx context.Context) (int, error) {
	rows, err := w.Pool.Query(ctx, `SELECT id, customer_id, kind, lang, payload, attempts, email_ct, first_name_ct, key_version
		FROM claim_notifications($1)`, w.Batch)
	if err != nil {
		return 0, err
	}
	batch, err := pgx.CollectRows(rows, pgx.RowToStructByPos[claimed])
	if err != nil {
		return 0, err
	}
	// Deliver in parallel with a small bound: each send opens its own SMTP connection and the pool is shared
	// safely, while the bound keeps a burst from hammering the mail server.
	sem := make(chan struct{}, max(1, w.Concurrency))
	var wg sync.WaitGroup
	for _, n := range batch {
		wg.Add(1)
		sem <- struct{}{}
		go func() {
			defer func() { <-sem; wg.Done() }()
			w.deliver(ctx, n)
		}()
	}
	wg.Wait()
	return len(batch), nil
}

var errNoAddress = errors.New("customer has no contact address")

func (w *Worker) deliver(ctx context.Context, n claimed) {
	ctx, span := otel.Tracer("disputes/notify").Start(ctx, "notify.send_email")
	defer span.End()
	span.SetAttributes(attribute.String("notify.kind", n.Kind), attribute.Int("notify.attempt", n.Attempts))

	err := w.send(ctx, n)
	var retry *int
	status := "sent"
	if err != nil {
		status = "failed"
		if !errors.Is(err, errNoAddress) && n.Attempts < w.MaxAttempts {
			secs := 30 * n.Attempts * n.Attempts // 30 s, 2 min, 4.5 min...
			retry, status = &secs, "retry"
		}
		span.SetStatus(codes.Error, "delivery failed")
		slog.WarnContext(ctx, "notifier: delivery failed", "id", n.ID, "kind", n.Kind, "attempt", n.Attempts, "status", status, "err", err)
	}
	telemetry.Notifications.WithLabelValues(n.Kind, status).Inc()
	if err == nil {
		slog.InfoContext(ctx, "notification sent", "id", n.ID, "kind", n.Kind, "lang", n.Lang, "attempt", n.Attempts)
	}

	msg := ""
	if err != nil {
		msg = err.Error()
	}
	if _, ferr := w.Pool.Exec(ctx, `SELECT finish_notification($1, $2, $3, $4)`, n.ID, err == nil, msg, retry); ferr != nil {
		slog.ErrorContext(ctx, "notifier: could not record result", "id", n.ID, "err", ferr)
	}
}

func (w *Worker) send(ctx context.Context, n claimed) error {
	if len(n.EmailCT) == 0 || n.KeyVersion == nil {
		return errNoAddress
	}
	to, err := w.PII.Decrypt(n.CustomerID, "email", *n.KeyVersion, n.EmailCT)
	if err != nil {
		return err
	}
	first, _ := w.PII.Decrypt(n.CustomerID, "first_name", *n.KeyVersion, n.FirstNameCT) // greeting is optional
	var payload map[string]string
	if err := json.Unmarshal(n.Payload, &payload); err != nil {
		return err
	}
	msg, err := Render(n.Kind, n.Lang, firstWord(first), w.AppURL, payload)
	if err != nil {
		return err
	}
	msg.To = to
	return w.Mailer.Send(ctx, msg)
}

// firstWord keeps "Samuel" from "Samuel Andrés": a friendlier greeting that reveals less.
func firstWord(s string) string {
	for i, r := range s {
		if r == ' ' {
			return s[:i]
		}
	}
	return s
}
