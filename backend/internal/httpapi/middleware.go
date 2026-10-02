package httpapi

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"regexp"
	"runtime/debug"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/logging"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
)

const requestIDHeader = "X-Request-ID"

// knownMethod keeps arbitrary client-sent methods out of metric labels.
func knownMethod(m string) string {
	switch m {
	case http.MethodGet, http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete, http.MethodOptions, http.MethodHead:
		return m
	}
	return "OTHER"
}

// A client-supplied request id is reused only if it looks like an id (no log injection through the header).
var validRequestID = regexp.MustCompile(`^[A-Za-z0-9._-]{8,64}$`)

type requestInfo struct{ role string }

type infoKey struct{}

// requestLog assigns the request id, returns it in X-Request-ID and writes one access-log line per request:
// method, route pattern, status, duration, size, client IP and caller role. Never the body, query values,
// headers or token.
func (s *Server) requestLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		id := r.Header.Get(requestIDHeader)
		if !validRequestID.MatchString(id) {
			id = newRequestID()
		}
		w.Header().Set(requestIDHeader, id)
		info := &requestInfo{role: "anonymous"}
		ip := s.clientIP(r)
		ctx := context.WithValue(logging.WithRequestID(r.Context(), id), infoKey{}, info)
		// The validated client IP goes to the audit trail (through the store) and to the trace; otelhttp's own
		// client.address trusts any X-Forwarded-For, so it is replaced with this one.
		ctx = store.WithClientIP(ctx, ip)
		trace.SpanFromContext(ctx).SetAttributes(attribute.String("client.address", ip))
		r = r.WithContext(ctx)

		ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)

		status := ww.Status()
		if status == 0 {
			status = http.StatusOK
		}
		route, pattern := r.URL.Path, "unmatched" // pattern: bounded label for metrics and span names
		if rc := chi.RouteContext(r.Context()); rc != nil && rc.RoutePattern() != "" {
			route, pattern = rc.RoutePattern(), rc.RoutePattern()
		}
		// otelhttp names the server span before routing ("GET"); name it after the route once chi has matched it.
		method := knownMethod(r.Method)
		span := trace.SpanFromContext(ctx)
		span.SetName(method + " " + pattern)
		span.SetAttributes(attribute.String("http.route", pattern))
		telemetry.HTTPRequests.WithLabelValues(pattern, method, strconv.Itoa(status)).Inc()
		telemetry.HTTPDuration.WithLabelValues(pattern, method).Observe(time.Since(start).Seconds())
		level := slog.LevelInfo
		switch {
		case route == "/api/health" || route == "/api/ready" || route == "/metrics":
			level = slog.LevelDebug // probes and scrapes every few seconds would drown the log
		case status >= 500:
			level = slog.LevelError
		case status >= 400:
			level = slog.LevelWarn
		}
		slog.Log(ctx, level, "http request",
			"method", r.Method, "route", route, "status", status,
			"duration_ms", time.Since(start).Milliseconds(), "bytes", ww.BytesWritten(),
			"client_ip", ip, "user_agent", truncate(r.UserAgent(), 120), "role", info.role)
	})
}

// notePrincipal records the caller's role for the access log (runs after token verification).
func notePrincipal(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if info, ok := r.Context().Value(infoKey{}).(*requestInfo); ok {
			if p, ok := auth.FromContext(r.Context()); ok {
				info.role = p.StaffRole()
				if info.role == "" {
					info.role = "customer"
				}
			}
		}
		next.ServeHTTP(w, r)
	})
}

// recoverer turns a panic into a logged error with its stack and a generic 500 for the client.
func recoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if v := recover(); v != nil {
				if v == http.ErrAbortHandler {
					panic(v)
				}
				slog.ErrorContext(r.Context(), "panic serving request", "panic", fmt.Sprint(v), "stack", string(debug.Stack()))
				writeError(w, http.StatusInternalServerError, "internal_error", "unexpected error; please try again")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// clientIP is the TCP peer, unless the peer is a trusted proxy (TRUSTED_PROXIES): then the right-most
// X-Forwarded-For address that is not itself a trusted proxy. A client can prepend anything to that header, so
// the left-most value is never trusted.
func (s *Server) clientIP(r *http.Request) string {
	peer, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		peer = r.RemoteAddr
	}
	if !s.trusted(peer) {
		return peer
	}
	hops := strings.Split(r.Header.Get("X-Forwarded-For"), ",")
	for i := len(hops) - 1; i >= 0; i-- {
		ip := strings.TrimSpace(hops[i])
		if net.ParseIP(ip) != nil && !s.trusted(ip) {
			return ip
		}
	}
	return peer
}

func (s *Server) trusted(ip string) bool {
	parsed := net.ParseIP(ip)
	for _, n := range s.TrustedProxies {
		if parsed != nil && n.Contains(parsed) {
			return true
		}
	}
	return false
}

// ParseCIDRs reads a comma-separated list like "10.0.0.0/8,172.16.0.0/12"; invalid entries are skipped.
func ParseCIDRs(list string) []*net.IPNet {
	var out []*net.IPNet
	for _, c := range strings.Split(list, ",") {
		if _, n, err := net.ParseCIDR(strings.TrimSpace(c)); err == nil {
			out = append(out, n)
		}
	}
	return out
}

func newRequestID() string {
	b := make([]byte, 12)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}
