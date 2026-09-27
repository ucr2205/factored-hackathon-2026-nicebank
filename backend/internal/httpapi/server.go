// Package httpapi exposes the orchestrator over HTTP (docs/api/contracts.md).
package httpapi

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"slices"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/orchestrator"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
)

type Server struct {
	Orch      *orchestrator.Orchestrator
	Verifier  *auth.Verifier
	Origins   []string
	ReadyFunc func(*http.Request) (int, map[string]string)
	Config    func(*http.Request) contract.AdminConfig
}

func (s *Server) Routes() http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID, middleware.RealIP, middleware.Recoverer, s.cors)

	r.Get("/api/health", func(w http.ResponseWriter, _ *http.Request) { writeJSON(w, http.StatusOK, map[string]string{"status": "ok"}) })
	r.Get("/api/ready", func(w http.ResponseWriter, r *http.Request) { code, body := s.ReadyFunc(r); writeJSON(w, code, body) })
	r.Handle("/metrics", promhttp.Handler())

	r.Group(func(r chi.Router) {
		r.Use(s.Verifier.Middleware(writeError))

		r.With(auth.RequireAnyRole(writeError, "customer")).Group(func(r chi.Router) {
			r.Post("/api/chat", s.chat)
			r.Post("/api/chat/confirm", s.confirm)
			r.Get("/api/sessions/{id}", s.session)
			r.Get("/api/me/overview", s.overview)
		})
		r.With(auth.RequireAnyRole(writeError, "agent", "supervisor")).Group(func(r chi.Router) {
			r.Get("/api/handoffs", s.listHandoffs)
			r.Get("/api/handoffs/{id}", s.getHandoff)
			r.Get("/api/sessions/{id}/audit", s.sessionAudit)
		})
		r.With(auth.RequireAnyRole(writeError, "agent")).Post("/api/handoffs/{id}/claim", s.claimHandoff)
		r.With(auth.RequireAnyRole(writeError, "agent")).Post("/api/handoffs/{id}/identity", s.revealIdentity)
		r.With(auth.RequireAnyRole(writeError, "supervisor")).Group(func(r chi.Router) {
			r.Get("/api/admin/config", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, http.StatusOK, s.Config(r)) })
			r.Get("/api/admin/summary", s.summary)
		})
	})
	return otelhttp.NewHandler(r, "http", otelhttp.WithFilter(func(r *http.Request) bool {
		return r.URL.Path != "/metrics" && r.URL.Path != "/api/health"
	}))
}

func (s *Server) chat(w http.ResponseWriter, r *http.Request) {
	var req contract.ChatRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 16<<10)).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "invalid JSON body")
		return
	}
	mode := "system"
	if r.URL.Query().Get("mode") == "baseline" {
		mode = "baseline"
	}
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.HandleMessage(r.Context(), p, req, mode)
	respond(w, out, err)
}

func (s *Server) confirm(w http.ResponseWriter, r *http.Request) {
	var req contract.ConfirmRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4<<10)).Decode(&req); err != nil || req.SessionID == "" || req.ActionID == "" {
		writeError(w, http.StatusBadRequest, "bad_request", "session_id and action_id are required")
		return
	}
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.Confirm(r.Context(), p, req)
	respond(w, out, err)
}

func (s *Server) session(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.Session(r.Context(), p, chi.URLParam(r, "id"))
	respond(w, out, err)
}

func (s *Server) overview(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.Overview(r.Context(), p)
	respond(w, out, err)
}

func (s *Server) listHandoffs(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.ListHandoffs(r.Context(), p, r.URL.Query().Get("status"))
	respond(w, out, err)
}

func (s *Server) getHandoff(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.GetHandoff(r.Context(), p, chi.URLParam(r, "id"))
	respond(w, out, err)
}

func (s *Server) claimHandoff(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.ClaimHandoff(r.Context(), p, chi.URLParam(r, "id"))
	respond(w, out, err)
}

// revealIdentity is a POST because every call writes an audit event.
func (s *Server) revealIdentity(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.RevealIdentity(r.Context(), p, chi.URLParam(r, "id"))
	respond(w, out, err)
}

func (s *Server) sessionAudit(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.SessionAudit(r.Context(), p, chi.URLParam(r, "id"))
	respond(w, out, err)
}

func (s *Server) summary(w http.ResponseWriter, r *http.Request) {
	p, _ := auth.FromContext(r.Context())
	out, err := s.Orch.Summary(r.Context(), p)
	respond(w, out, err)
}

func respond(w http.ResponseWriter, body any, err error) {
	switch {
	case err == nil:
		writeJSON(w, http.StatusOK, body)
	case errors.Is(err, orchestrator.ErrSessionExpired):
		writeError(w, http.StatusUnauthorized, "session_expired", "the conversation expired; start a new one")
	case errors.Is(err, orchestrator.ErrStepUpRequired):
		writeJSON(w, http.StatusForbidden, map[string]string{"error": "step_up_required", "acr": "2",
			"message": "this action requires a verification code"})
	case errors.Is(err, orchestrator.ErrNotFound):
		writeError(w, http.StatusNotFound, "not_found", "not found")
	case errors.Is(err, orchestrator.ErrBadRequest):
		writeError(w, http.StatusBadRequest, "bad_request", "invalid request for the current conversation state")
	case errors.Is(err, store.ErrNoCustomer):
		writeError(w, http.StatusForbidden, "forbidden", "token has no customer identity")
	default:
		slog.Error("request failed", "err", err)
		writeError(w, http.StatusServiceUnavailable, "dependency_unavailable", "temporary problem; please try again")
	}
}

func (s *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if origin := r.Header.Get("Origin"); slices.Contains(s.Origins, origin) {
			h := w.Header()
			h.Set("Access-Control-Allow-Origin", origin)
			h.Set("Vary", "Origin")
			h.Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
			h.Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			h.Set("Access-Control-Expose-Headers", "traceparent")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"error": code, "message": msg})
}
