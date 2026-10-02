// Command api is the disputes backend: identity, sessions, orchestration, policy engine, tools and audit.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/config"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/httpapi"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/logging"
	"github.com/factored-hackathon-2026/disputes/backend/internal/mlclient"
	"github.com/factored-hackathon-2026/disputes/backend/internal/notify"
	"github.com/factored-hackathon-2026/disputes/backend/internal/orchestrator"
	"github.com/factored-hackathon-2026/disputes/backend/internal/pii"
	"github.com/factored-hackathon-2026/disputes/backend/internal/policy"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
)

func main() {
	cfg := config.Load()
	logger := logging.New(os.Stdout, logging.ParseLevel(cfg.LogLevel), cfg.LogFormat)
	slog.SetDefault(logger)
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
	var model llm.Provider = llm.Fake{}
	switch cfg.LLMProvider {
	case "fake":
	case "deepseek":
		if cfg.LLMAPIKey == "" {
			slog.Error("LLM_PROVIDER=deepseek needs DEEPSEEK_API_KEY in the environment (.env); refusing to start")
			os.Exit(1)
		}
		model = llm.NewDeepSeek(cfg.LLMBaseURL, cfg.LLMAPIKey, cfg.LLMModel, cfg.LLMFallbackModel, cfg.LLMComposeWithAI)
	default:
		slog.Error("unknown LLM_PROVIDER; refusing to start", "provider", cfg.LLMProvider)
		os.Exit(1)
	}
	slog.Info("llm provider", "provider", model.Name(), "version", model.Version())
	orch := orchestrator.New(db, pol, ml, model, cfg.DemoToday, cfg.SessionIdle)
	telemetry.Preinit()
	prometheus.MustRegister(orch.QueueCollector())
	if orch.PII, err = pii.New(cfg.PIIKey, 1); err != nil {
		slog.Error("PII_KEY missing or invalid (run `make env`); refusing to start", "err", err)
		os.Exit(1)
	}

	if cfg.NotifyEnabled {
		mailer, err := newMailer(cfg)
		if err != nil {
			slog.Error("email notifications misconfigured; refusing to start", "err", err)
			os.Exit(1)
		}
		worker := &notify.Worker{Pool: db.Pool, PII: orch.PII, Mailer: mailer, Interval: cfg.NotifyPollInterval, Batch: 10, MaxAttempts: 4,
			AppURL: cfg.MailAppURL, Concurrency: 3}
		go worker.Run(ctx)
		slog.Info("email notifications on", "smtp_host", cfg.SMTPHost, "security", cfg.SMTPSecurity,
			"from", cfg.MailFrom, "redirected", cfg.MailRedirectTo != "")
	}

	srv := &httpapi.Server{
		Orch:           orch,
		Verifier:       auth.NewVerifier(ctx, cfg.OIDCIssuer, cfg.OIDCJWKSURL, cfg.OIDCAudience),
		Origins:        cfg.AllowedOrigins,
		TrustedProxies: httpapi.ParseCIDRs(cfg.TrustedProxies),
		DocsEnabled:    cfg.DocsEnabled,
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
		ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second,
		ErrorLog: slog.NewLogLogger(logger.Handler(), slog.LevelWarn)} // net/http's own errors, as JSON too
	go func() {
		slog.Info("backend listening", "addr", cfg.HTTPAddr, "policy_version", pol.Version, "log_level", cfg.LogLevel,
			"docs", cfg.DocsEnabled, "trusted_proxies", cfg.TrustedProxies != "")
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

// newMailer validates the SMTP settings. A real server (TLS) needs credentials, and every message is redirected
// to MAIL_REDIRECT_TO unless MAIL_ALLOW_REAL_RECIPIENTS=true: the demo data holds realistic-looking addresses.
func newMailer(cfg config.Config) (*notify.SMTPMailer, error) {
	switch cfg.SMTPSecurity {
	case "none":
	case "ssl", "starttls":
		if cfg.EmailUsername == "" || cfg.EmailPassword == "" {
			return nil, errors.New("EMAIL_USERNAME and EMAIL_PASSWORD are required for a real SMTP server")
		}
		if cfg.MailRedirectTo == "" && !cfg.MailAllowRealRcpt {
			return nil, errors.New("set MAIL_REDIRECT_TO (test inbox) or MAIL_ALLOW_REAL_RECIPIENTS=true")
		}
	default:
		return nil, errors.New("SMTP_SECURITY must be ssl, starttls or none")
	}
	return &notify.SMTPMailer{Host: cfg.SMTPHost, Port: cfg.SMTPPort, Security: cfg.SMTPSecurity,
		Username: cfg.EmailUsername, Password: cfg.EmailPassword, From: cfg.MailFrom, FromName: cfg.MailFromName,
		RedirectTo: cfg.MailRedirectTo, Bcc: cfg.MailBcc}, nil
}
