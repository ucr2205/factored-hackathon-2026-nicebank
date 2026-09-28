package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"gopkg.in/yaml.v3"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/logging"
)

// captureLogs points the default logger at a buffer for the duration of a test.
func captureLogs(t *testing.T) *bytes.Buffer {
	t.Helper()
	var buf bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(logging.New(&buf, slog.LevelDebug, "json"))
	t.Cleanup(func() { slog.SetDefault(prev) })
	return &buf
}

func lastLog(t *testing.T, buf *bytes.Buffer) map[string]any {
	t.Helper()
	lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
	var m map[string]any
	if err := json.Unmarshal([]byte(lines[len(lines)-1]), &m); err != nil {
		t.Fatalf("bad log line %q: %v", lines[len(lines)-1], err)
	}
	return m
}

func testRouter(s *Server, h http.HandlerFunc) http.Handler {
	r := chi.NewRouter()
	r.Use(s.requestLog, recoverer)
	r.Get("/api/things/{id}", h)
	return r
}

func TestAccessLogAndRequestID(t *testing.T) {
	logs := captureLogs(t)
	s := &Server{}
	h := testRouter(s, func(w http.ResponseWriter, r *http.Request) {
		if logging.RequestID(r.Context()) == "" {
			t.Error("request id missing from the handler context")
		}
		writeError(w, http.StatusNotFound, "not_found", "not found")
	})

	req := httptest.NewRequest(http.MethodGet, "/api/things/42?secret=x", nil)
	req.Header.Set("Authorization", "Bearer should-not-appear")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	id := rec.Header().Get(requestIDHeader)
	if len(id) < 8 {
		t.Fatalf("no X-Request-ID returned: %q", id)
	}
	var body map[string]string
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	if body["request_id"] != id {
		t.Errorf("error body request_id = %q, header %q", body["request_id"], id)
	}
	m := lastLog(t, logs)
	if m["msg"] != "http request" || m["route"] != "/api/things/{id}" || m["status"] != float64(404) ||
		m["level"] != "WARN" || m["request_id"] != id || m["method"] != "GET" {
		t.Fatalf("unexpected access log: %v", m)
	}
	if strings.Contains(logs.String(), "should-not-appear") || strings.Contains(logs.String(), "secret=x") {
		t.Fatal("token or query string leaked into the log")
	}
}

func TestClientRequestIDIsReusedOnlyWhenSafe(t *testing.T) {
	captureLogs(t)
	h := testRouter(&Server{}, func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) })
	for in, reuse := range map[string]bool{"client-abc-123456": true, "bad\nid injected": false, "x": false} {
		req := httptest.NewRequest(http.MethodGet, "/api/things/1", nil)
		req.Header.Set(requestIDHeader, in)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if got := rec.Header().Get(requestIDHeader); (got == in) != reuse {
			t.Errorf("%q: got %q, reuse=%v", in, got, reuse)
		}
	}
}

func TestPanicIsLoggedAndAnswered500(t *testing.T) {
	logs := captureLogs(t)
	h := testRouter(&Server{}, func(http.ResponseWriter, *http.Request) { panic("boom") })
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/things/1", nil))
	if rec.Code != http.StatusInternalServerError || !strings.Contains(rec.Body.String(), "internal_error") {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(logs.String(), `"msg":"panic serving request"`) || !strings.Contains(logs.String(), `"stack"`) {
		t.Fatalf("panic not logged with stack: %s", logs.String())
	}
	if m := lastLog(t, logs); m["status"] != float64(500) || m["level"] != "ERROR" {
		t.Fatalf("access log after panic: %v", m)
	}
}

func TestClientIPTrustsOnlyConfiguredProxies(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "172.18.0.5:51000"
	req.Header.Set("X-Forwarded-For", "6.6.6.6, 203.0.113.9")

	if got := (&Server{}).clientIP(req); got != "172.18.0.5" {
		t.Errorf("without trusted proxies the header must be ignored, got %s", got)
	}
	s := &Server{TrustedProxies: ParseCIDRs("172.16.0.0/12, not-a-cidr")}
	if got := s.clientIP(req); got != "203.0.113.9" {
		t.Errorf("right-most untrusted hop expected, got %s (a client can prepend fake values)", got)
	}
}

// Every route the router serves is documented in openapi.yaml, and the spec documents nothing that is not served.
func TestOpenAPICoversAllRoutes(t *testing.T) {
	var spec struct {
		Paths map[string]map[string]any `yaml:"paths"`
	}
	if err := yaml.Unmarshal(openAPISpec, &spec); err != nil {
		t.Fatal(err)
	}
	documented := map[string]bool{}
	for path, ops := range spec.Paths {
		for method := range ops {
			documented[strings.ToUpper(method)+" "+path] = true
		}
	}
	s := &Server{Verifier: auth.NewVerifier(context.Background(), "http://issuer.test", "http://issuer.test/jwks", "disputes-api")}
	served := map[string]bool{}
	_ = chi.Walk(s.router(), func(method, route string, _ http.Handler, _ ...func(http.Handler) http.Handler) error {
		if route != "/api/docs" && route != "/api/openapi.yaml" {
			served[method+" "+route] = true
		}
		return nil
	})
	for k := range served {
		if !documented[k] {
			t.Errorf("route %s is not documented in openapi.yaml", k)
		}
	}
	for k := range documented {
		if !served[k] {
			t.Errorf("openapi.yaml documents %s, which the router does not serve", k)
		}
	}
}
