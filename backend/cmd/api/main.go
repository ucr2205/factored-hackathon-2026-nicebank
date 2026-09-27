// Command api is the disputes backend: identity, sessions, orchestration, policy engine, tools and audit.
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/config"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/httpapi"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/mlclient"
	"github.com/factored-hackathon-2026/disputes/backend/internal/orchestrator"
	"github.com/factored-hackathon-2026/disputes/backend/internal/policy"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	pol, err := policy.Load(cfg.PolicyFile)
	if err != nil {
		slog.Error("invalid policy; refusing to start", "err", err)
		os.Exit(1)
	}
	shutdownTracing, err := telemetry.InitTracing(ctx, "disputes-backend")
	if err != nil {
		slog.Warn("tracing disabled", "err", err)
	}
	db, err := store.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		slog.Error("database", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	ml := mlclient.New(cfg.MLServiceURL)
	var model llm.Provider = llm.Fake{} // real provider plugged in on D2 behind the same interface
	orch := orchestrator.New(db, pol, ml, model, cfg.DemoToday, cfg.SessionIdle)

	srv := &httpapi.Server{
		Orch:     orch,
		Verifier: auth.NewVerifier(ctx, cfg.OIDCIssuer, cfg.OIDCJWKSURL, cfg.OIDCAudience),
		Origins:  cfg.AllowedOrigins,
		ReadyFunc: func(r *http.Request) (int, map[string]string) {
			status := map[string]string{"status": "ready", "database": "ok", "ml_service": "ok"}
			code := http.StatusOK
			if err := db.Pool.Ping(r.Context()); err != nil {
				status["database"], status["status"], code = "unreachable", "degraded", http.StatusServiceUnavailable
			}
			if ml.ModelVersion(r.Context()) == "unavailable" {
				status["ml_service"], status["status"], code = "unreachable", "degraded", http.StatusServiceUnavailable
			}
			return code, status
		},
		Config: func(r *http.Request) contract.AdminConfig {
			return contract.AdminConfig{PolicyVersion: pol.Version, PolicyOrigin: pol.Origin, Policy: pol,
				LLMProvider: model.Name(), PromptVersion: model.Version(), ClassifierModel: ml.ModelVersion(r.Context()),
				DemoToday: cfg.DemoToday.Format(time.DateOnly)}
		},
	}

	httpSrv := &http.Server{Addr: cfg.HTTPAddr, Handler: srv.Routes(), ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second}
	go func() {
		slog.Info("backend listening", "addr", cfg.HTTPAddr, "policy_version", pol.Version)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server failed", "err", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpSrv.Shutdown(shutdownCtx)
	if shutdownTracing != nil {
		_ = shutdownTracing(shutdownCtx)
	}
}
