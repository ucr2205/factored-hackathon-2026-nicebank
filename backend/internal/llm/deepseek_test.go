package llm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// fakeAPI answers chat completions with the given content per model; an empty content means HTTP 500.
func fakeAPI(t *testing.T, byModel map[string]string, seen *[]string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req chatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatal(err)
		}
		if r.Header.Get("Authorization") != "Bearer test-key" || req.ResponseFormat["type"] != "json_object" || req.Thinking["type"] != "disabled" {
			t.Errorf("unexpected request: auth=%q format=%v thinking=%v", r.Header.Get("Authorization"), req.ResponseFormat, req.Thinking)
		}
		*seen = append(*seen, req.Model)
		content, ok := byModel[req.Model]
		if !ok || content == "" {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(map[string]any{
			"choices": []any{map[string]any{"message": map[string]string{"content": content}}},
			"usage":   map[string]int{"prompt_tokens": 1000, "completion_tokens": 50, "prompt_cache_miss_tokens": 1000},
		})
	}))
}

func TestDeepSeekExtract(t *testing.T) {
	var seen []string
	srv := fakeAPI(t, map[string]string{
		"deepseek-flash": `{"amount": 1450, "date_from": "2026-06-15", "date_to": null, "merchant_hint": "electro mundo"}`,
	}, &seen)
	defer srv.Close()
	d := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", false)

	ex, u, err := d.Extract(context.Background(), "No reconozco una compra de 1.450 dólares del lunes", "es", today)
	if err != nil || ex.Amount == nil || *ex.Amount != 1450 || ex.DateFrom.Day() != 15 || ex.DateTo.Day() != 15 || ex.MerchantHint != "electro mundo" {
		t.Fatalf("got %+v err=%v", ex, err)
	}
	if u.InputTokens != 1000 || u.CostUSD <= 0 {
		t.Errorf("usage not recorded: %+v", u)
	}
}

func TestDeepSeekFallsBackToSecondModelThenToFake(t *testing.T) {
	var seen []string
	srv := fakeAPI(t, map[string]string{"deepseek-v4-pro": `{"amount": 89.9, "date_from": "2026-06-16", "date_to": "2026-06-16"}`}, &seen)
	defer srv.Close()

	d := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "deepseek-v4-pro", false)
	ex, _, _ := d.Extract(context.Background(), "me cobraram duas vezes 89,90 ontem", "pt", today)
	if ex.Amount == nil || *ex.Amount != 89.9 || strings.Join(seen, ",") != "deepseek-flash,deepseek-v4-pro" {
		t.Fatalf("fallback model not used: %+v seen=%v", ex, seen)
	}

	// Both models down: the deterministic extractor still answers, so the turn is never blocked.
	down := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", false)
	ex, _, err := down.Extract(context.Background(), "me cobraram duas vezes 89,90 ontem", "pt", today)
	if err != nil || ex.Amount == nil || *ex.Amount != 89.9 {
		t.Fatalf("fake fallback failed: %+v err=%v", ex, err)
	}
}

func TestDeepSeekDiscardsImplausibleDates(t *testing.T) {
	var seen []string
	srv := fakeAPI(t, map[string]string{"deepseek-flash": `{"amount": null, "date_from": "2027-01-01", "date_to": null}`}, &seen)
	defer srv.Close()
	ex, _, _ := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", false).Extract(context.Background(), "un cargo raro", "es", today)
	if ex.DateFrom != nil || ex.Amount != nil {
		t.Fatalf("future date must be dropped: %+v", ex)
	}
}

func TestDeepSeekPickUsesLocalMatchFirst(t *testing.T) {
	var seen []string
	srv := fakeAPI(t, map[string]string{"deepseek-flash": `{"index": 3}`}, &seen)
	defer srv.Close()
	d := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", false)
	merchants := []string{"Mercado Central", "Farmacia Salud", "Cine Plus"}

	if i, _, _ := d.PickCandidate(context.Background(), "la segunda", merchants); i != 1 || len(seen) != 0 {
		t.Fatalf("ordinal should resolve locally: i=%d calls=%v", i, seen)
	}
	if i, _, _ := d.PickCandidate(context.Background(), "a do filme", merchants); i != 2 || len(seen) != 1 {
		t.Fatalf("model pick: i=%d calls=%v", i, seen)
	}
}

func TestDeepSeekComposeKeepsVerifiedFacts(t *testing.T) {
	facts := map[string]string{"case_id": "DSP-000123", "amount": "$ 1.200,00", "merchant": "Mercado Central"}
	in := ComposeInput{Intent: "case_opened", Lang: "es", Facts: facts}
	template, _, _ := Fake{}.Compose(context.Background(), in)

	for name, content := range map[string]string{
		"keeps facts":  `{"reply": "Listo, abrí la disputa DSP-000123 por $ 1.200,00 en Mercado Central."}`,
		"drops a fact": `{"reply": "Listo, abrí tu disputa por $ 1.200,00 en Mercado Central."}`,
	} {
		var seen []string
		srv := fakeAPI(t, map[string]string{"deepseek-flash": content}, &seen)
		got, _, _ := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", true).Compose(context.Background(), in)
		srv.Close()
		if name == "keeps facts" && got == template {
			t.Errorf("%s: expected the model rewrite", name)
		}
		if name == "drops a fact" && got != template {
			t.Errorf("%s: expected the template, got %q", name, got)
		}
	}

	// Template mode never calls the model.
	var seen []string
	srv := fakeAPI(t, map[string]string{}, &seen)
	defer srv.Close()
	if got, _, _ := NewDeepSeek(srv.URL, "test-key", "deepseek-flash", "", false).Compose(context.Background(), in); got != template || len(seen) != 0 {
		t.Fatalf("template mode called the model: %v", seen)
	}
}
