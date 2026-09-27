// Package telemetry sets up OpenTelemetry tracing (OTLP/HTTP to the collector) and Prometheus metrics.
// No personal data goes into span attributes or metric labels.
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
)
