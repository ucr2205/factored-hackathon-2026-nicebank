// Package mlclient calls ml-service (contract C2) with a timeout and bounded retries.
package mlclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Classification struct {
	Label        string  `json:"label"`
	Confidence   float64 `json:"confidence"`
	Abstain      bool    `json:"abstain"`
	ModelVersion string  `json:"model_version"`
}

type Client struct {
	baseURL string
	http    *http.Client
	retries int
}

func New(baseURL string) *Client {
	return &Client{baseURL: baseURL, http: &http.Client{Timeout: 2 * time.Second}, retries: 2}
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
		err = json.NewDecoder(resp.Body).Decode(&out)
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
	_ = json.NewDecoder(resp.Body).Decode(&h)
	return h.ModelVersion
}
