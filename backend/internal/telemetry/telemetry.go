// Package telemetry sets up OpenTelemetry tracing (OTLP/HTTP to the collector) and Prometheus metrics.
// No personal data goes into span attributes or metric labels.
//
// Pipeline role: cross-cutting. Each turn is one "chat.turn" span with a child span per audited step, and the
// counters below measure outcomes, tool verification, model usage and cost per turn.
package telemetry

import (
	"context"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

// InitTracing exports spans to OTEL_EXPORTER_OTLP_ENDPOINT (read by the exporter from the environment).
func InitTracing(ctx context.Context, service string) (func(context.Context) error, error) {
	exp, err := otlptracehttp.New(ctx)
	if err != nil {
		return nil, err
	}
	res, _ := resource.Merge(resource.Default(), resource.NewWithAttributes(semconv.SchemaURL, semconv.ServiceName(service)))
	tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exp), sdktrace.WithResource(res))
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	return tp.Shutdown, nil
}

// Prometheus metrics. Labels are bounded enums (language, outcome, mode, tool, status, route pattern), never ids.
var (
	ChatTurns = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "chat_turns_total", Help: "Chat turns by final outcome.",
	}, []string{"lang", "outcome", "mode"})
	ToolCalls = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "tool_calls_total", Help: "Bank tool calls by result.",
	}, []string{"tool", "status"})
	TurnDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name: "chat_turn_duration_seconds", Help: "End-to-end duration of a chat turn.",
		Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8},
	}, []string{"mode"})
	LLMTokens = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "llm_tokens_total", Help: "Tokens used by the language model provider.",
	}, []string{"provider", "direction"})
	LLMCalls = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "llm_calls_total", Help: "Language model calls by model, operation and result.",
	}, []string{"provider", "model", "op", "status"})
	SpeculativeExtractions = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "llm_speculative_extractions_total", Help: "Extractions started alongside classification: used or discarded.",
	}, []string{"outcome"})
	Notifications = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "notifications_total", Help: "Customer email notifications by kind and delivery result.",
	}, []string{"kind", "status"})
	PIIMaskDegraded = promauto.NewCounter(prometheus.CounterOpts{
		Name: "pii_mask_degraded_total", Help: "Turns where customer names could not be decrypted for masking.",
	})
	LLMCost = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "llm_cost_usd_total", Help: "Language model spend in USD (list prices, cache hits included).",
	}, []string{"provider", "model"})
	// route is the chi pattern ("/api/handoffs/{id}"), never the raw path, so the label set stays bounded.
	HTTPRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "http_requests_total", Help: "HTTP requests by route pattern, method and status code.",
	}, []string{"route", "method", "status"})
	HTTPDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name: "http_request_duration_seconds", Help: "HTTP request duration by route pattern.",
		Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8},
	}, []string{"route", "method"})
)

// Preinit creates the known label combinations at zero, so every series exists (and can be graphed or
// alerted on) before the first chat turn instead of appearing only after traffic.
func Preinit() {
	for _, lang := range []string{"es", "pt"} {
		for _, outcome := range []string{"resolve", "clarify", "abstain", "escalate", "confirm"} {
			for _, mode := range []string{"system", "baseline"} {
				ChatTurns.WithLabelValues(lang, outcome, mode)
			}
		}
	}
	for _, mode := range []string{"system", "baseline"} {
		TurnDuration.WithLabelValues(mode)
	}
	ToolCalls.WithLabelValues("find_transactions", "ok")
	for _, tool := range []string{"open_dispute_case", "block_card"} {
		for _, status := range []string{"verified", "not_verified"} {
			ToolCalls.WithLabelValues(tool, status)
		}
	}
	for _, kind := range []string{"case_opened", "card_blocked", "handoff_created"} {
		for _, status := range []string{"sent", "retry", "failed"} {
			Notifications.WithLabelValues(kind, status)
		}
	}
	for _, outcome := range []string{"used", "discarded"} {
		SpeculativeExtractions.WithLabelValues(outcome)
	}
}
