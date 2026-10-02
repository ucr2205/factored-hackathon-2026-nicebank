// Package logging configures structured logs (log/slog) for the backend.
//
// Every record logged with a context (slog.InfoContext and friends) carries the request_id and the OpenTelemetry
// trace_id/span_id, so a log line leads to its trace in Jaeger and to the X-Request-ID the client saw. Attributes
// whose key looks like personal data or a secret are redacted, as a safety net: callers must still never log
// message text, names, emails, tokens or card data.
//
// Pipeline role: cross-cutting. The orchestrator writes one "chat turn" line per turn (outcome, rule ids,
// latency, cost); the audit trail, not the log, is the record of what each step did.
package logging

import (
	"context"
	"io"
	"log/slog"
	"strings"

	"go.opentelemetry.io/otel/trace"
)

type ctxKey struct{}

// WithRequestID stores the request id for later log records.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxKey{}, id)
}

// RequestID returns the request id stored in ctx, or "".
func RequestID(ctx context.Context) string {
	id, _ := ctx.Value(ctxKey{}).(string)
	return id
}

// ParseLevel maps "debug" | "info" | "warn" | "error" to a slog level (default info).
func ParseLevel(s string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	}
	return slog.LevelInfo
}

// New builds the process logger: JSON by default (one object per line, for log shippers), "text" for humans.
func New(w io.Writer, level slog.Level, format string) *slog.Logger {
	opts := &slog.HandlerOptions{Level: level, ReplaceAttr: redact}
	var h slog.Handler = slog.NewJSONHandler(w, opts)
	if strings.EqualFold(format, "text") {
		h = slog.NewTextHandler(w, opts)
	}
	return slog.New(contextHandler{h})
}

// sensitive key fragments (substring match) and exact keys: matching attributes become "[redacted]".
// Short words like "pan" are exact-only, so "span_id" survives.
var sensitive = []string{"password", "secret", "token", "authorization", "cookie", "api_key", "apikey",
	"email", "first_name", "last_name", "full_name", "document", "phone", "card_number", "message_text", "reply_text"}

var sensitiveExact = map[string]bool{"pan": true, "cvv": true, "pin": true, "otp": true, "totp": true}

func redact(_ []string, a slog.Attr) slog.Attr {
	k := strings.ToLower(a.Key)
	if sensitiveExact[k] {
		return slog.String(a.Key, "[redacted]")
	}
	for _, s := range sensitive {
		if strings.Contains(k, s) {
			return slog.String(a.Key, "[redacted]")
		}
	}
	return a
}

// contextHandler adds request_id, trace_id and span_id from the record's context.
type contextHandler struct{ slog.Handler }

// Handle adds the request and trace ids to the record, then delegates.
func (h contextHandler) Handle(ctx context.Context, r slog.Record) error {
	if id := RequestID(ctx); id != "" {
		r.AddAttrs(slog.String("request_id", id))
	}
	if sc := trace.SpanContextFromContext(ctx); sc.IsValid() {
		r.AddAttrs(slog.String("trace_id", sc.TraceID().String()), slog.String("span_id", sc.SpanID().String()))
	}
	return h.Handler.Handle(ctx, r)
}

// WithAttrs keeps the wrapper so derived loggers still get request and trace ids.
func (h contextHandler) WithAttrs(as []slog.Attr) slog.Handler {
	return contextHandler{h.Handler.WithAttrs(as)}
}

// WithGroup keeps the wrapper so derived loggers still get request and trace ids.
func (h contextHandler) WithGroup(n string) slog.Handler {
	return contextHandler{h.Handler.WithGroup(n)}
}
