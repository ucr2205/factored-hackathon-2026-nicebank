package llm

import (
	"context"
	"strings"
	"testing"
	"time"
)

var today = time.Date(2026, 6, 17, 23, 59, 0, 0, time.UTC) // a Wednesday

func TestExtractAmountAndDate(t *testing.T) {
	cases := []struct {
		text    string
		amount  float64
		dateDay int
	}{
		{"No reconozco un cobro de 1.200 pesos del martes", 1200, 16},
		{"me cobraram duas vezes 89,90 ontem", 89.90, 16},
		{"cargo de $450.50 el 10/06", 450.50, 10},
		{"no reconozco un cargo de ayer", 0, 16},
		{"No reconozco el cargo de 324,48 en Teatro Nacional del 23/12", 324.48, 23},
	}
	for _, c := range cases {
		ex, _, _ := Fake{}.Extract(context.Background(), c.text, "es", today)
		if c.amount == 0 && ex.Amount != nil {
			t.Errorf("%q: unexpected amount %v", c.text, *ex.Amount)
		}
		if c.amount != 0 && (ex.Amount == nil || *ex.Amount != c.amount) {
			t.Errorf("%q: amount = %v, want %v", c.text, ex.Amount, c.amount)
		}
		if ex.DateFrom == nil || ex.DateFrom.Day() != c.dateDay {
			t.Errorf("%q: date = %v, want day %d", c.text, ex.DateFrom, c.dateDay)
		}
		if ex.DateFrom != nil && ex.DateFrom.After(today) {
			t.Errorf("%q: date %v is in the future", c.text, ex.DateFrom)
		}
	}
}

// A day and month without a year is the most recent past occurrence: "23/12" on 2026-06-17 is 2025-12-23.
func TestDateWithoutYearIsInThePast(t *testing.T) {
	ex, _, _ := Fake{}.Extract(context.Background(), "te acabo de dar la fecha de 23/12", "es", today)
	if ex.DateFrom == nil || ex.DateFrom.Format("2006-01-02") != "2025-12-23" {
		t.Fatalf("date = %v, want 2025-12-23", ex.DateFrom)
	}
	ex, _, _ = Fake{}.Extract(context.Background(), "el 23/12/2024", "es", today)
	if ex.DateFrom == nil || ex.DateFrom.Year() != 2024 {
		t.Fatalf("explicit year must be kept: %v", ex.DateFrom)
	}
}

func TestPickCandidate(t *testing.T) {
	merchants := []string{"Mercado Central", "Farmacia Salud", "Cine Plus"}
	for text, want := range map[string]int{"la segunda": 1, "a primeira": 0, "fue en farmácia salud": 1, "no sé": -1} {
		if got, _, _ := (Fake{}).PickCandidate(context.Background(), text, merchants); got != want {
			t.Errorf("%q: got %d, want %d", text, got, want)
		}
	}
}

func TestComposeUsesLanguage(t *testing.T) {
	out, _, _ := Fake{}.Compose(context.Background(), ComposeInput{Intent: "clarify_multi", Lang: "pt", Facts: map[string]string{"count": "2"}})
	if out != "Encontrei 2 movimentações que podem ser. Qual delas você quer contestar?" {
		t.Fatalf("unexpected: %s", out)
	}
}

func TestEveryTemplateHasSpanishAndPortuguese(t *testing.T) {
	for intent, byLang := range templates {
		for _, lang := range []string{"es", "pt"} {
			if byLang[lang] == "" {
				t.Errorf("template %s has no %s text", intent, lang)
			}
		}
	}
}

func TestExplainTemplatesShowTheRecord(t *testing.T) {
	facts := map[string]string{"amount": "42,37 USD", "merchant": "Streaming Music", "date": "12 de junio", "last4": "2457"}
	for _, intent := range []string{"explain_reversed", "explain_declined", "explain_pending", "confirm_block_declined"} {
		for _, lang := range []string{"es", "pt"} {
			out, _, _ := Fake{}.Compose(context.Background(), ComposeInput{Intent: intent, Lang: lang, Facts: facts})
			if !strings.Contains(out, "42,37 USD") || !strings.Contains(out, "Streaming Music") || strings.Contains(out, "{") {
				t.Errorf("%s/%s does not show the verified record: %s", intent, lang, out)
			}
		}
	}
}
