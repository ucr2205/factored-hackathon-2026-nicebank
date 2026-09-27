package llm

import (
	"context"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/textnorm"
)

// Fake is a deterministic stand-in for a real model: regex extraction and fixed es/pt templates.
// It keeps development and evaluation free and reproducible until the real provider is chosen.
type Fake struct{}

func (Fake) Name() string    { return "fake" }
func (Fake) Version() string { return "fake-templates-v1" }

var (
	amountRe = regexp.MustCompile(`(?i)(?:r\$|us\$|\$)?\s?(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?:\s?(?:pesos|reais|reales|dolares|usd|mxn|cop|ars))?`)
	dateRe   = regexp.MustCompile(`\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b`)
	weekdays = map[string]time.Weekday{
		"domingo": time.Sunday, "lunes": time.Monday, "martes": time.Tuesday, "miercoles": time.Wednesday,
		"jueves": time.Thursday, "viernes": time.Friday, "sabado": time.Saturday,
		"segunda": time.Monday, "terca": time.Tuesday, "quarta": time.Wednesday, "quinta": time.Thursday,
		"sexta": time.Friday,
	}
	ordinals = []struct {
		words []string
		index int
	}{
		{[]string{"primera", "primero", "primeira", "1", "uno", "um"}, 0},
		{[]string{"segunda", "segundo", "2", "dos", "dois"}, 1},
		{[]string{"tercera", "tercero", "terceira", "terceiro", "3", "tres"}, 2},
		{[]string{"cuarta", "cuarto", "quarta", "quarto", "4"}, 3},
		{[]string{"quinta", "quinto", "5"}, 4},
		{[]string{"ultima", "ultimo"}, -2},
	}
)

// Normalize is re-exported for callers that match text the same way the fake model does.
var Normalize = textnorm.Normalize

func (Fake) Extract(_ context.Context, text, _ string, today time.Time) (Extraction, Usage, error) {
	n := Normalize(text)
	var ex Extraction
	day := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	setDay := func(d time.Time) {
		from, to := d, d.Add(24*time.Hour-time.Second)
		ex.DateFrom, ex.DateTo = &from, &to
	}

	switch {
	case strings.Contains(n, "anteayer") || strings.Contains(n, "anteontem"):
		setDay(day.AddDate(0, 0, -2))
	case strings.Contains(n, "ayer") || strings.Contains(n, "ontem"):
		setDay(day.AddDate(0, 0, -1))
	case strings.Contains(n, "hoy") || strings.Contains(n, "hoje"):
		setDay(day)
	case strings.Contains(n, "semana pasada") || strings.Contains(n, "semana passada"):
		from, to := day.AddDate(0, 0, -14), day.AddDate(0, 0, -7)
		ex.DateFrom, ex.DateTo = &from, &to
	}
	if ex.DateFrom == nil {
		for word, wd := range weekdays {
			// "segunda"/"quinta" are also ordinals; only treat them as weekdays next to "feira" or "el/la/na".
			if (word == "segunda" || word == "quinta" || word == "quarta") && !strings.Contains(n, word+"-feira") && !strings.Contains(n, word+" feira") {
				continue
			}
			if regexp.MustCompile(`\b` + word + `\b`).MatchString(n) {
				back := (int(day.Weekday()) - int(wd) + 7) % 7
				if back == 0 {
					back = 7
				}
				setDay(day.AddDate(0, 0, -back))
				break
			}
		}
	}
	if ex.DateFrom == nil {
		if m := dateRe.FindStringSubmatch(n); m != nil {
			d, _ := strconv.Atoi(m[1])
			mo, _ := strconv.Atoi(m[2])
			y := day.Year()
			if m[3] != "" {
				y, _ = strconv.Atoi(m[3])
				if y < 100 {
					y += 2000
				}
			}
			if mo >= 1 && mo <= 12 && d >= 1 && d <= 31 {
				date := time.Date(y, time.Month(mo), d, 0, 0, 0, 0, time.UTC)
				if m[3] == "" && date.After(day) {
					date = date.AddDate(-1, 0, 0) // no year given: the most recent past occurrence
				}
				setDay(date)
			}
		}
	}

	// Amounts: skip numbers that belong to a date expression.
	cleaned := dateRe.ReplaceAllString(n, " ")
	for _, m := range amountRe.FindAllStringSubmatch(cleaned, -1) {
		if v, ok := parseAmount(m[1], m[2]); ok && v >= 1 {
			ex.Amount = &v
			break
		}
	}
	return ex, Usage{}, nil
}

// parseAmount handles "1.200", "1,200", "89,90", "89.90" and "1.234,56".
func parseAmount(intPart, decPart string) (float64, bool) {
	digits := strings.NewReplacer(".", "", ",", "").Replace(intPart)
	v, err := strconv.ParseFloat(digits, 64)
	if err != nil {
		return 0, false
	}
	if decPart != "" {
		d, _ := strconv.ParseFloat("0."+decPart, 64)
		v += d
	}
	return v, true
}

func (Fake) PickCandidate(_ context.Context, text string, merchants []string) (int, Usage, error) {
	n := Normalize(text)
	for i, m := range merchants {
		if m != "" && strings.Contains(n, Normalize(m)) {
			return i, Usage{}, nil
		}
	}
	for _, o := range ordinals {
		for _, w := range o.words {
			if regexp.MustCompile(`\b` + w + `\b`).MatchString(n) {
				if o.index == -2 {
					return len(merchants) - 1, Usage{}, nil
				}
				if o.index < len(merchants) {
					return o.index, Usage{}, nil
				}
			}
		}
	}
	return -1, Usage{}, nil
}

func (Fake) Compose(_ context.Context, in ComposeInput) (string, Usage, error) {
	tpl, ok := templates[in.Intent][in.Lang]
	if !ok {
		tpl = templates[in.Intent]["es"]
	}
	pairs := make([]string, 0, len(in.Facts)*2)
	for k, v := range in.Facts {
		pairs = append(pairs, "{"+k+"}", v)
	}
	return strings.NewReplacer(pairs...).Replace(tpl), Usage{}, nil
}

var templates = map[string]map[string]string{
	"abstain_scope": {
		"es": "Por este canal solo puedo ayudarte con cargos que no reconoces o disputas de tarjeta. Para préstamos, inversiones o cambios de datos, contáctanos en la app de NiceBank o en una sucursal.",
		"pt": "Por este canal só posso ajudar com cobranças não reconhecidas ou contestações de cartão. Para empréstimos, investimentos ou alteração de dados, fale com a NiceBank pelo app ou em uma agência.",
	},
	"abstain_injection": {
		"es": "No puedo cambiar mis instrucciones ni ejecutar acciones fuera del proceso de disputas. Si tienes un cargo que no reconoces, cuéntame la fecha, el monto o el comercio.",
		"pt": "Não posso mudar minhas instruções nem executar ações fora do processo de contestação. Se você tem uma cobrança não reconhecida, me diga a data, o valor ou o estabelecimento.",
	},
	"clarify_type": {
		"es": "Quiero asegurarme de entenderte. ¿Qué pasó con el cargo: no lo reconoces, se cobró dos veces, el monto es incorrecto, no recibiste la compra, o te robaron la tarjeta?",
		"pt": "Quero ter certeza de que entendi. O que aconteceu com a cobrança: você não reconhece, foi cobrada duas vezes, o valor está errado, não recebeu a compra, ou o cartão foi roubado?",
	},
	"clarify_notfound": {
		"es": "No encontré ese movimiento en tus tarjetas. ¿Me das la fecha aproximada, el monto o el nombre del comercio?",
		"pt": "Não encontrei essa movimentação nos seus cartões. Pode me dizer a data aproximada, o valor ou o nome do estabelecimento?",
	},
	"clarify_notfound_searched": {
		"es": "No encontré ningún movimiento{searched} en tus tarjetas. ¿Me confirmas la fecha y el monto, o me dices el nombre del comercio?",
		"pt": "Não encontrei nenhuma movimentação{searched} nos seus cartões. Pode confirmar a data e o valor, ou me dizer o nome do estabelecimento?",
	},
	"clarify_multi": {
		"es": "Encontré {count} movimientos que podrían ser. ¿Cuál es el que quieres disputar?",
		"pt": "Encontrei {count} movimentações que podem ser. Qual delas você quer contestar?",
	},
	"confirm_open_case": {
		"es": "Encontré el cargo de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4}. ¿Confirmas que abra una disputa por \"{type}\"?",
		"pt": "Encontrei a cobrança de {amount} em {merchant} de {date} no seu cartão final {last4}. Confirma que eu abra uma contestação por \"{type}\"?",
	},
	"confirm_block_card": {
		"es": "Por tu seguridad, te recomiendo bloquear la tarjeta terminada en {last4} y pasar tu caso a un especialista. Para bloquearla te pediré un código de verificación. ¿Confirmas el bloqueo?",
		"pt": "Para sua segurança, recomendo bloquear o cartão final {last4} e encaminhar seu caso a um especialista. Para bloquear, vou pedir um código de verificação. Confirma o bloqueio?",
	},
	"case_opened": {
		"es": "Listo: abrí la disputa {case_id} por el cargo de {amount} en {merchant}. Verifiqué que el caso quedó registrado. Te avisaremos por la app cuando haya novedades.",
		"pt": "Pronto: abri a contestação {case_id} da cobrança de {amount} em {merchant}. Verifiquei que o caso ficou registrado. Avisaremos pelo app quando houver novidades.",
	},
	"case_exists": {
		"es": "Ese cargo de {amount} en {merchant} ya tiene la disputa {case_id} abierta, así que no abrí otra. Te avisaremos por la app cuando haya novedades.",
		"pt": "Essa cobrança de {amount} em {merchant} já tem a contestação {case_id} aberta, então não abri outra. Avisaremos pelo app quando houver novidades.",
	},
	"card_blocked_handoff": {
		"es": "Bloqueé tu tarjeta terminada en {last4} (referencia {block_id}) y verifiqué el bloqueo. Un especialista de NiceBank ya tiene tu caso con todos los datos y te contactará.",
		"pt": "Bloqueei seu cartão final {last4} (referência {block_id}) e verifiquei o bloqueio. Um especialista da NiceBank já está com seu caso e todos os dados, e entrará em contato.",
	},
	"handoff_created": {
		"es": "Tu caso necesita revisión de un especialista. Ya le pasé los datos verificados y te contactará pronto; no hace falta que repitas la información.",
		"pt": "Seu caso precisa da análise de um especialista. Já repassei os dados verificados e ele entrará em contato em breve; você não precisa repetir as informações.",
	},
	"declined": {
		"es": "Entendido, no hice ningún cambio. Si quieres retomarlo, escríbeme.",
		"pt": "Entendido, não fiz nenhuma alteração. Se quiser retomar, é só me escrever.",
	},
	"declined_handoff": {
		"es": "Entendido, no bloqueé la tarjeta. Igual pasé tu caso a un especialista, que te contactará pronto.",
		"pt": "Entendido, não bloqueei o cartão. Mesmo assim encaminhei seu caso a um especialista, que entrará em contato em breve.",
	},
	"tech_failure": {
		"es": "Tengo un problema técnico para revisar tu caso ahora. Para no dejarte sin respuesta, lo pasé a un especialista que te contactará.",
		"pt": "Estou com um problema técnico para analisar seu caso agora. Para não deixar você sem resposta, encaminhei a um especialista que entrará em contato.",
	},
	"action_failed": {
		"es": "No pude confirmar que la acción se completó, así que no la doy por hecha. Pasé tu caso a un especialista.",
		"pt": "Não consegui confirmar que a ação foi concluída, então não a considero feita. Encaminhei seu caso a um especialista.",
	},
}
