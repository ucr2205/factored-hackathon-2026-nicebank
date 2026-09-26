// Command api is the disputes backend: identity, sessions, orchestration, policy engine, tools and audit.
// Phase 0: health, readiness (checks ml-service) and Prometheus metrics.
package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	addr := envOr("HTTP_ADDR", ":8081")
	mlURL := envOr("ML_SERVICE_URL", "http://localhost:8000")

	r := chi.NewRouter()
	r.Use(middleware.RequestID, middleware.RealIP, middleware.Recoverer)
	r.Use(middleware.Timeout(15 * time.Second))

	r.Get("/api/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	r.Get("/api/ready", readyHandler(mlURL))
	r.Handle("/metrics", promhttp.Handler())

	srv := &http.Server{Addr: addr, Handler: r, ReadHeaderTimeout: 5 * time.Second}

	go func() {
		slog.Info("backend listening", "addr", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server failed", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}

// readyHandler reports whether the backend's dependencies are reachable.
func readyHandler(mlURL string) http.HandlerFunc {
	client := &http.Client{Timeout: 2 * time.Second}
	return func(w http.ResponseWriter, r *http.Request) {
		req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, mlURL+"/health", nil)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"status": "error"})
			return
		}
		resp, err := client.Do(req)
		if err != nil || resp.StatusCode != http.StatusOK {
			writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "degraded", "ml_service": "unreachable"})
			return
		}
		resp.Body.Close()
		writeJSON(w, http.StatusOK, map[string]string{"status": "ready", "ml_service": "ok"})
	}
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
