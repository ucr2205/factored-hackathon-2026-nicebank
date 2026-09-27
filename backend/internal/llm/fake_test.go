package llm

import (
	"context"
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
