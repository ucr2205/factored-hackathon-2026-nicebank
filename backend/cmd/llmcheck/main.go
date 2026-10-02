// Command llmcheck compares LLM providers on fact extraction (amount, date, merchant) over labeled ES/PT
// customer messages, and reports accuracy, latency and cost per provider. It calls the real DeepSeek API when
// DEEPSEEK_API_KEY is set (a full run costs well under one US cent); otherwise only the fake provider runs.
//
// Usage (from backend/): go run ./cmd/llmcheck [-models deepseek-flash,deepseek-v4-pro]
//
// Pipeline role: offline measurement of the Understand step's fact extraction (llm.Provider.Extract).
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/guard"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
)

// today matches DEMO_TODAY (the end of the synthetic dataset), a Wednesday.
var today = time.Date(2026, 6, 17, 23, 59, 0, 0, time.UTC)

type expect struct {
	amount   float64 // 0 = no amount in the message
	from, to string  // expected date range (YYYY-MM-DD); "" = no date
	merchant string  // expected merchant hint substring (lowercase); "" = not checked
}

type testCase struct {
	lang, text string
	want       expect
}

var cases = []testCase{
	{"es", "No reconozco un cobro de 1.200 pesos del martes", expect{1200, "2026-06-16", "2026-06-16", ""}},
	{"es", "me cobraron dos veces 89,90 ayer", expect{89.90, "2026-06-16", "2026-06-16", ""}},
	{"es", "No reconozco el cargo de 324,48 en Teatro Nacional del 23/12", expect{324.48, "2025-12-23", "2025-12-23", "teatro nacional"}},
	{"es", "hay un cargo raro de $450.50 el 10/06", expect{450.50, "2026-06-10", "2026-06-10", ""}},
	{"es", "no reconozco una compra de mil quinientos dólares de hoy", expect{1500, "2026-06-17", "2026-06-17", ""}},
	{"es", "el lunes me cobraron 38 dólares en Streaming Music", expect{38, "2026-06-15", "2026-06-15", "streaming music"}},
	{"es", "me robaron la tarjeta", expect{}},
	{"es", "el cajero no me dio los 2.000 pesos anteayer", expect{2000, "2026-06-15", "2026-06-15", ""}},
	{"es", "cobro de 99,99 del 3 de enero que no hice", expect{99.99, "2026-01-03", "2026-01-03", ""}},
	{"es", "compré unos zapatos el 5 de mayo por 165,50 y nunca llegaron", expect{165.50, "2026-05-05", "2026-05-05", ""}},
	{"pt", "Me cobraram duas vezes no Mercado Central ontem, 89,90", expect{89.90, "2026-06-16", "2026-06-16", "mercado central"}},
	{"pt", "Não reconheço uma compra de R$ 250,00 de segunda-feira", expect{250, "2026-06-15", "2026-06-15", ""}},
	{"pt", "tem uma cobrança de 1.450 dólares que eu não fiz, foi na segunda-feira", expect{1450, "2026-06-15", "2026-06-15", ""}},
	{"pt", "cobrança estranha de 72,35 no dia 12/06", expect{72.35, "2026-06-12", "2026-06-12", ""}},
	{"pt", "roubaram meu cartão hoje", expect{0, "2026-06-17", "2026-06-17", ""}},
	{"pt", "não recebi a compra de trezentos reais da semana passada", expect{300, "2026-06-03", "2026-06-10", ""}},
	// Added 30 Sep (P3): amounts in words, dates without a year, merchants with typos. The merchant check is a
	// substring that holds for both the typo and its correction (e.g. "netfl" matches "Netflx" and "Netflix").
	{"es", "me cobraron doscientos cincuenta dólares el 2 de junio en Farmacia Salud", expect{250, "2026-06-02", "2026-06-02", "farmacia salud"}},
	{"es", "no reconozco un cargo de mil doscientos pesos del 28 de mayo", expect{1200, "2026-05-28", "2026-05-28", ""}},
	{"es", "hay un cobro de 75,40 en Netflx que no hice, fue el sábado", expect{75.40, "2026-06-13", "2026-06-13", "netfl"}},
	{"es", "el 15/05 me cobraron dos veces 320 en Supermercado La Estrela", expect{320, "2026-05-15", "2026-05-15", "la estrel"}},
	{"es", "me descontaron ochocientos cincuenta en el cajero ayer y no salió la plata", expect{850, "2026-06-16", "2026-06-16", ""}},
	{"pt", "não reconheço uma compra de quatrocentos e vinte reais do dia 3 de junho", expect{420, "2026-06-03", "2026-06-03", ""}},
	{"pt", "cobraram duas vezes 59,90 na Amazom anteontem", expect{59.90, "2026-06-15", "2026-06-15", "amazo"}},
	{"pt", "comprei um fone por cento e oitenta reais em 25 de maio e não chegou", expect{180, "2026-05-25", "2026-05-25", ""}},
	{"pt", "tem uma cobrança de R$ 1.299,00 do Magazine Brasl que eu não fiz", expect{1299, "", "", "magazine bras"}},
	{"pt", "o caixa eletrônico não liberou os 600 reais na sexta passada", expect{600, "2026-06-12", "2026-06-12", ""}},
}

type score struct {
	name                         string
	amountOK, dateOK, merchantOK int
	merchantTotal, failures      int
	latencies                    []time.Duration
	cost                         float64
	misses                       []string
}

func main() {
	models := flag.String("models", "deepseek-flash,deepseek-v4-pro", "comma-separated DeepSeek models to compare")
	flag.Parse()

	providers := []llm.Provider{llm.Fake{}}
	if key := os.Getenv("DEEPSEEK_API_KEY"); key != "" {
		for _, m := range strings.Split(*models, ",") {
			providers = append(providers, llm.NewDeepSeek("https://api.deepseek.com", key, strings.TrimSpace(m), "", false))
		}
	} else {
		fmt.Println("DEEPSEEK_API_KEY not set: running the fake provider only.")
	}

	var results []score
	for _, p := range providers {
		s := score{name: p.Version()}
		for _, c := range cases {
			started := time.Now()
			ex, u, _ := p.Extract(context.Background(), guard.Mask(c.text), c.lang, "", today)
			s.latencies = append(s.latencies, time.Since(started))
			s.cost += u.CostUSD
			if p.Name() == "deepseek" && u.InputTokens == 0 {
				s.failures++ // the call failed and the provider fell back to the fake extractor
			}
			ok := judge(c, ex, &s)
			if !ok {
				s.misses = append(s.misses, fmt.Sprintf("[%s] %q -> %s", c.lang, c.text, describe(ex)))
			}
		}
		results = append(results, s)
	}

	fmt.Printf("\n%d labeled messages (ES %d / PT %d), today = %s\n\n", len(cases), count("es"), count("pt"), today.Format(time.DateOnly))
	fmt.Printf("%-36s %8s %8s %9s %8s %8s %10s %6s\n", "provider", "amount", "date", "merchant", "p50", "p95", "cost USD", "fails")
	for _, s := range results {
		fmt.Printf("%-36s %7d%% %7d%% %8d%% %8s %8s %10.5f %6d\n", s.name, pct(s.amountOK, len(cases)), pct(s.dateOK, len(cases)),
			pct(s.merchantOK, s.merchantTotal), percentile(s.latencies, 50), percentile(s.latencies, 95), s.cost, s.failures)
	}
	for _, s := range results {
		if len(s.misses) > 0 {
			fmt.Printf("\n%s misses:\n  %s\n", s.name, strings.Join(s.misses, "\n  "))
		}
	}
}

func judge(c testCase, ex llm.Extraction, s *score) bool {
	amountOK := (c.want.amount == 0 && ex.Amount == nil) || (ex.Amount != nil && abs(*ex.Amount-c.want.amount) < 0.01)
	dateOK := (c.want.from == "" && ex.DateFrom == nil) ||
		(ex.DateFrom != nil && ex.DateFrom.Format(time.DateOnly) == c.want.from && ex.DateTo.Format(time.DateOnly) == c.want.to)
	merchantOK := true
	if c.want.merchant != "" {
		s.merchantTotal++
		merchantOK = strings.Contains(strings.ToLower(ex.MerchantHint), c.want.merchant)
		if merchantOK {
			s.merchantOK++
		}
	}
	if amountOK {
		s.amountOK++
	}
	if dateOK {
		s.dateOK++
	}
	return amountOK && dateOK && merchantOK
}

func describe(ex llm.Extraction) string {
	parts := []string{}
	if ex.Amount != nil {
		parts = append(parts, fmt.Sprintf("amount=%.2f", *ex.Amount))
	}
	if ex.DateFrom != nil {
		parts = append(parts, "date="+ex.DateFrom.Format(time.DateOnly)+".."+ex.DateTo.Format(time.DateOnly))
	}
	if ex.MerchantHint != "" {
		parts = append(parts, "merchant="+ex.MerchantHint)
	}
	if len(parts) == 0 {
		return "(nothing)"
	}
	return strings.Join(parts, " ")
}

func count(lang string) int {
	n := 0
	for _, c := range cases {
		if c.lang == lang {
			n++
		}
	}
	return n
}

func pct(n, total int) int {
	if total == 0 {
		return 0
	}
	return 100 * n / total
}

func percentile(d []time.Duration, p int) string {
	s := append([]time.Duration(nil), d...)
	sort.Slice(s, func(i, j int) bool { return s[i] < s[j] })
	return s[(len(s)-1)*p/100].Round(time.Millisecond).String()
}

func abs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}
