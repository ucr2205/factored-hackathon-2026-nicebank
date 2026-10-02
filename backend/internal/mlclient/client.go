// Package mlclient calls ml-service (contract C2) with a timeout and bounded retries.
//
// Pipeline role: Understand. The orchestrator classifies every masked customer message into the C6 taxonomy;
// an abstention makes it ask the customer, and a failure after the retries escalates to a human (ESC-TECH-01).
package mlclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

const maxResponseBytes = 64 << 10

// Classification is the C2 response of POST /classify. Abstain is true below the service's confidence threshold.
type Classification struct {
	Label        string  `json:"label"`
	Confidence   float64 `json:"confidence"`
	Abstain      bool    `json:"abstain"`
	ModelVersion string  `json:"model_version"`
}

// Client calls ml-service over HTTP with tracing, a per-attempt timeout and bounded retries.
type Client struct {
	baseURL string
	http    *http.Client
	retries int
}

// New returns a Client for the ml-service at baseURL (e.g. http://ml-service:8000).
func New(baseURL string) *Client {
	// 3 s per attempt: a warm classification takes ~20-50 ms, but a cold one took ~1.4 s and must not fail the turn.
	// The otelhttp transport adds an "ml.classify" client span per attempt and propagates the trace context.
	transport := otelhttp.NewTransport(http.DefaultTransport, otelhttp.WithSpanNameFormatter(
		func(_ string, r *http.Request) string { return "ml" + strings.ReplaceAll(r.URL.Path, "/", ".") }))
	return &Client{baseURL: baseURL, http: &http.Client{Timeout: 3 * time.Second, Transport: transport}, retries: 2}
}

// Classify tries once plus up to two retries with backoff; the caller falls back to a human on error.
func (c *Client) Classify(ctx context.Context, maskedText, lang string) (Classification, error) {
	body, _ := json.Marshal(map[string]string{"text": maskedText, "lang": lang})
	var lastErr error
	for attempt := 0; attempt <= c.retries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return Classification{}, ctx.Err()
			case <-time.After(time.Duration(100*attempt*attempt) * time.Millisecond):
			}
		}
		req, _ := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/classify", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		var out Classification
		err = json.NewDecoder(io.LimitReader(resp.Body, maxResponseBytes)).Decode(&out)
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK || err != nil {
			lastErr = fmt.Errorf("classify: status %d: %v", resp.StatusCode, err)
			continue
		}
		return out, nil
	}
	return Classification{}, lastErr
}

// ModelVersion reads the model version from /health (best effort, for the supervisor view).
func (c *Client) ModelVersion(ctx context.Context) string {
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	resp, err := c.http.Do(req)
	if err != nil {
		return "unavailable"
	}
	defer resp.Body.Close()
	var h struct {
		ModelVersion string `json:"model_version"`
	}
	_ = json.NewDecoder(io.LimitReader(resp.Body, maxResponseBytes)).Decode(&h)
	return h.ModelVersion
}
