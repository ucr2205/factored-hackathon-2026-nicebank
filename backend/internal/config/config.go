// Package config reads the backend configuration from environment variables.
package config

import (
	"os"
	"strconv"
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
}

func Load() Config {
	today, err := time.Parse("2006-01-02", envOr("DEMO_TODAY", "2026-06-17"))
	if err != nil {
		today = time.Now().UTC()
	}
	idle, _ := strconv.Atoi(envOr("SESSION_IDLE_MINUTES", "15"))
	return Config{
		HTTPAddr:       envOr("HTTP_ADDR", ":8081"),
		DatabaseURL:    envOr("DATABASE_URL", "postgres://app_user:change-me-app@localhost:5433/bank"),
		MLServiceURL:   envOr("ML_SERVICE_URL", "http://localhost:8000"),
		OIDCIssuer:     envOr("OIDC_ISSUER", "http://localhost:8080/realms/latam-bank"),
		OIDCJWKSURL:    envOr("OIDC_JWKS_URL", "http://localhost:8080/realms/latam-bank/protocol/openid-connect/certs"),
		OIDCAudience:   envOr("OIDC_AUDIENCE", "disputes-api"),
		PolicyFile:     envOr("POLICY_FILE", "../policies/disputes.yaml"),
		AllowedOrigins: []string{envOr("ALLOWED_ORIGIN", "http://localhost:5173"), "http://localhost:8088"},
		DemoToday:      today.Add(23*time.Hour + 59*time.Minute),
		SessionIdle:    time.Duration(idle) * time.Minute,
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
