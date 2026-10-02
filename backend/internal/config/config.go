// Package config reads the backend configuration from environment variables.
package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	HTTPAddr       string
	DatabaseURL    string
	MLServiceURL   string
	OIDCIssuer     string // issuer as it appears in tokens (browser-facing URL)
	OIDCJWKSURL    string // where the backend fetches signing keys (may be an internal URL)
	OIDCAudience   string
	PolicyFile     string
	AllowedOrigins []string
	DemoToday      time.Time // "today" for relative dates, aligned with the end of the synthetic dataset
	SessionIdle    time.Duration

	LLMProvider      string // "fake" (default) or "deepseek"
	LLMBaseURL       string
	LLMAPIKey        string // from DEEPSEEK_API_KEY; only ever read from the environment
	LLMModel         string
	LLMFallbackModel string
	LLMComposeWithAI bool

	PIIKey string // base64 32-byte AES key for customer_identity (PII_KEY); environment only

	// Email notifications. Defaults target the local Mailpit; a real server needs SMTP_SECURITY=ssl|starttls,
	// credentials (EMAIL_USERNAME / EMAIL_PASSWORD) and MAIL_REDIRECT_TO unless MAIL_ALLOW_REAL_RECIPIENTS=true.
	NotifyEnabled      bool
	SMTPHost           string
	SMTPPort           int
	SMTPSecurity       string // ssl | starttls | none
	EmailUsername      string
	EmailPassword      string
	MailFrom           string
	MailFromName       string
	MailRedirectTo     string
	MailBcc            []string
	MailAllowRealRcpt  bool
	NotifyPollInterval time.Duration
	MailAppURL         string // link in the emails' button (the customer app)

	LogLevel       string // debug | info | warn | error
	LogFormat      string // json (default) | text
	TrustedProxies string // CIDRs whose X-Forwarded-For is trusted; empty = the TCP peer is the client
	DocsEnabled    bool   // serve /api/docs and /api/openapi.yaml
}

func Load() Config {
	today, err := time.Parse("2006-01-02", envOr("DEMO_TODAY", "2026-06-17"))
	if err != nil {
		today = time.Now().UTC()
	}
	idle, _ := strconv.Atoi(envOr("SESSION_IDLE_MINUTES", "15"))
	smtpPort, _ := strconv.Atoi(envOr("SMTP_PORT", "1025"))
	return Config{
		HTTPAddr:       envOr("HTTP_ADDR", ":8081"),
		DatabaseURL:    envOr("DATABASE_URL", "postgres://app_user:change-me-app@localhost:5433/bank"),
		MLServiceURL:   envOr("ML_SERVICE_URL", "http://localhost:8000"),
		OIDCIssuer:     envOr("OIDC_ISSUER", "http://localhost:8080/realms/latam-bank"),
		OIDCJWKSURL:    envOr("OIDC_JWKS_URL", "http://localhost:8080/realms/latam-bank/protocol/openid-connect/certs"),
		OIDCAudience:   envOr("OIDC_AUDIENCE", "disputes-api"),
		PolicyFile:     envOr("POLICY_FILE", "../policies/disputes.yaml"),
		// The dev server, the container build and the gateway (PUBLIC_URL, the public entry point).
		AllowedOrigins: []string{envOr("ALLOWED_ORIGIN", "http://localhost:5173"), "http://localhost:8088",
			envOr("PUBLIC_URL", "http://localhost:8090")},
		DemoToday:      today.Add(23*time.Hour + 59*time.Minute),
		SessionIdle:    time.Duration(idle) * time.Minute,

		LLMProvider:      envOr("LLM_PROVIDER", "fake"),
		LLMBaseURL:       envOr("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
		LLMAPIKey:        os.Getenv("DEEPSEEK_API_KEY"),
		LLMModel:         envOr("LLM_MODEL", "deepseek-flash"),
		LLMFallbackModel: os.Getenv("LLM_FALLBACK_MODEL"),
		LLMComposeWithAI: os.Getenv("LLM_COMPOSE") == "ai",

		PIIKey: os.Getenv("PII_KEY"),

		NotifyEnabled:      envOr("NOTIFY_ENABLED", "true") == "true",
		SMTPHost:           envOr("SMTP_HOST", "localhost"),
		SMTPPort:           smtpPort,
		SMTPSecurity:       envOr("SMTP_SECURITY", "none"),
		EmailUsername:      os.Getenv("EMAIL_USERNAME"),
		EmailPassword:      os.Getenv("EMAIL_PASSWORD"),
		MailFrom:           envOr("MAIL_FROM", "nicebank@evon.solutions"),
		MailFromName:       envOr("MAIL_FROM_NAME", "NiceBank"),
		MailRedirectTo:     os.Getenv("MAIL_REDIRECT_TO"),
		MailBcc:            splitList(os.Getenv("MAIL_BCC")),
		MailAllowRealRcpt:  os.Getenv("MAIL_ALLOW_REAL_RECIPIENTS") == "true",
		NotifyPollInterval: 3 * time.Second,
		MailAppURL:         envOr("MAIL_APP_URL", "http://localhost:8088/chat"),

		LogLevel:       envOr("LOG_LEVEL", "info"),
		LogFormat:      envOr("LOG_FORMAT", "json"),
		TrustedProxies: os.Getenv("TRUSTED_PROXIES"),
		DocsEnabled:    envOr("DOCS_ENABLED", "true") == "true",
	}
}

func splitList(s string) []string {
	var out []string
	for _, v := range strings.Split(s, ",") {
		if v = strings.TrimSpace(v); v != "" {
			out = append(out, v)
		}
	}
	return out
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
