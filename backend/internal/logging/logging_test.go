package logging

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"testing"

	"go.opentelemetry.io/otel/trace"
)

func decode(t *testing.T, b *bytes.Buffer) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(b.Bytes(), &m); err != nil {
		t.Fatalf("not JSON: %q (%v)", b.String(), err)
	}
	return m
}

func TestContextAddsRequestAndTraceIDs(t *testing.T) {
	var buf bytes.Buffer
	log := New(&buf, slog.LevelInfo, "json")
	tid, _ := trace.TraceIDFromHex("4bf92f3577b34da6a3ce929d0e0e4736")
	sid, _ := trace.SpanIDFromHex("00f067aa0ba902b7")
	ctx := trace.ContextWithSpanContext(WithRequestID(context.Background(), "req-12345678"),
		trace.NewSpanContext(trace.SpanContextConfig{TraceID: tid, SpanID: sid, TraceFlags: trace.FlagsSampled}))

	log.InfoContext(ctx, "chat turn", "outcome", "resolve")
	m := decode(t, &buf)
	if m["request_id"] != "req-12345678" || m["trace_id"] != tid.String() || m["span_id"] != sid.String() || m["outcome"] != "resolve" {
		t.Fatalf("missing correlation fields: %v", m)
	}
}

func TestSensitiveKeysAreRedacted(t *testing.T) {
	var buf bytes.Buffer
	log := New(&buf, slog.LevelInfo, "json")
	log.Info("oops", "email", "rosa@example.test", "Authorization", "Bearer abc", "api_key", "sk-123",
		"first_name", "Rosa", "message_text", "no reconozco", "pan", "4111", "status", 200)
	m := decode(t, &buf)
	for _, k := range []string{"email", "Authorization", "api_key", "first_name", "message_text", "pan"} {
		if m[k] != "[redacted]" {
			t.Errorf("%s not redacted: %v", k, m[k])
		}
	}
	if m["status"] != float64(200) {
		t.Errorf("non-sensitive attribute changed: %v", m["status"])
	}
}

func TestLevels(t *testing.T) {
	var buf bytes.Buffer
	log := New(&buf, ParseLevel("warn"), "json")
	log.Info("hidden")
	if buf.Len() != 0 {
		t.Fatalf("info must be filtered at warn level: %q", buf.String())
	}
	for in, want := range map[string]slog.Level{"debug": slog.LevelDebug, "INFO": slog.LevelInfo, "warning": slog.LevelWarn, "error": slog.LevelError, "": slog.LevelInfo} {
		if got := ParseLevel(in); got != want {
			t.Errorf("ParseLevel(%q) = %v, want %v", in, got, want)
		}
	}
}
