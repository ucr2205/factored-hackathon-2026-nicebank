package orchestrator

import (
	"testing"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/tools"
)

func TestMoneyUsesSpanishSeparators(t *testing.T) {
	for in, want := range map[float64]string{1250000: "1.250.000,00 COP", 316.254: "316,25 COP", 0.5: "0,50 COP", 3952.5679: "3.952,57 COP"} {
		if got := money(in, "COP", "es"); got != want {
			t.Errorf("money(%v) = %q, want %q", in, got, want)
		}
	}
}

func TestStaffAmountShowsBothCurrenciesAndTheRate(t *testing.T) {
	day := time.Date(2026, 6, 12, 0, 0, 0, 0, time.UTC)
	cop := tools.Transaction{Amount: 1250000, Currency: "COP"}
	got := staffAmount(cop, tools.Conversion{USD: 316.25, Rate: 0.000253, RateDate: day})
	want := "Monto: 1.250.000,00 COP = 316,25 USD · tasa 1 USD = 3.952,57 COP (1 COP = 0,000253 USD) del 12/06/2026"
	if got != want {
		t.Fatalf("got  %q\nwant %q", got, want)
	}
	if got := staffAmount(tools.Transaction{Amount: 987.65, Currency: "USD"}, tools.Conversion{USD: 987.65, Rate: 1}); got != "Monto: 987,65 USD (sin conversión)" {
		t.Fatalf("USD amount: %q", got)
	}
	if got := staffAmount(cop, tools.Conversion{USD: 316.25}); got != "Monto: 1.250.000,00 COP = 316,25 USD (equivalente del dataset, sin tasa del día)" {
		t.Fatalf("no-rate fallback: %q", got)
	}
}
