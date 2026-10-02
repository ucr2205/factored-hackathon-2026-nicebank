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

// Name identifies the provider in logs, metrics and audit rows.
func (Fake) Name() string { return "fake" }

// Version identifies the template set.
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

// Extract reads relative dates (hoy/ayer/ontem, weekdays, "semana pasada"), dd/mm[/yy] dates and the first
// amount that is not part of a date, from Spanish or Portuguese text.
func (Fake) Extract(_ context.Context, text, _, _ string, today time.Time) (Extraction, Usage, error) {
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

// PickCandidate matches a merchant name contained in the reply, then ordinal words ("la segunda", "a última").
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

// Compose fills the reviewed template for the intent: regional variant first, then the language, then Spanish.
func (Fake) Compose(_ context.Context, in ComposeInput) (string, Usage, error) {
	// Regional wording first (es-AR: vos, es-CO: usted), then the language, then Spanish.
	tpl, ok := templates[in.Intent][in.Lang+"-"+countryCode[in.Country]]
	if !ok {
		tpl, ok = templates[in.Intent][in.Lang]
	}
	if !ok {
		tpl = templates[in.Intent]["es"]
	}
	pairs := make([]string, 0, len(in.Facts)*2)
	for k, v := range in.Facts {
		pairs = append(pairs, "{"+k+"}", v)
	}
	return strings.NewReplacer(pairs...).Replace(tpl), Usage{}, nil
}

// countryCode maps the bank record's country to the template variant suffix. Mexico uses the base Spanish (tú).
var countryCode = map[string]string{"Argentina": "AR", "Colombia": "CO"}

var templates = map[string]map[string]string{
	"abstain_scope": {
		"es":    "Por este canal solo puedo ayudarte con cargos que no reconoces o disputas de tarjeta. Para préstamos, inversiones o cambios de datos, contáctanos en la app de NiceBank o en una sucursal.",
		"pt":    "Por este canal só posso ajudar com cobranças não reconhecidas ou contestações de cartão. Para empréstimos, investimentos ou alteração de dados, fale com a NiceBank pelo app ou em uma agência.",
		"es-AR": "Por este canal solo puedo ayudarte con cargos que no reconocés o disputas de tarjeta. Para préstamos, inversiones o cambios de datos, contactanos en la app de NiceBank o en una sucursal.",
		"es-CO": "Por este canal solo puedo ayudarle con cargos que no reconoce o disputas de tarjeta. Para préstamos, inversiones o cambios de datos, comuníquese con nosotros en la app de NiceBank o en una oficina.",
	},
	"abstain_injection": {
		"es":    "No puedo cambiar mis instrucciones ni ejecutar acciones fuera del proceso de disputas. Si tienes un cargo que no reconoces, cuéntame la fecha, el monto o el comercio.",
		"pt":    "Não posso mudar minhas instruções nem executar ações fora do processo de contestação. Se você tem uma cobrança não reconhecida, me diga a data, o valor ou o estabelecimento.",
		"es-AR": "No puedo cambiar mis instrucciones ni ejecutar acciones fuera del proceso de disputas. Si tenés un cargo que no reconocés, contame la fecha, el monto o el comercio.",
		"es-CO": "No puedo cambiar mis instrucciones ni ejecutar acciones fuera del proceso de disputas. Si tiene un cargo que no reconoce, cuénteme la fecha, el monto o el comercio.",
	},
	"abstain_third_party": {
		"es":    "Solo puedo ayudarte con tus propias tarjetas y cuentas, no con las de otra persona. Si esa persona tiene un problema, puede escribirnos desde su propia sesión. ¿Tienes algún cargo tuyo que revisar?",
		"pt":    "Só posso ajudar com os seus próprios cartões e contas, não com os de outra pessoa. Se essa pessoa tiver um problema, ela pode falar com a gente pela própria sessão. Você tem alguma cobrança sua para revisar?",
		"es-AR": "Solo puedo ayudarte con tus propias tarjetas y cuentas, no con las de otra persona. Si esa persona tiene un problema, puede escribirnos desde su propia sesión. ¿Tenés algún cargo tuyo para revisar?",
		"es-CO": "Solo puedo ayudarle con sus propias tarjetas y cuentas, no con las de otra persona. Si esa persona tiene un problema, puede escribirnos desde su propia sesión. ¿Tiene algún cargo suyo para revisar?",
	},
	"clarify_type": {
		"es":    "Quiero asegurarme de entenderte. ¿Qué pasó con el cargo: no lo reconoces, se cobró dos veces, el monto es incorrecto, no recibiste la compra, o te robaron la tarjeta?",
		"pt":    "Quero ter certeza de que entendi. O que aconteceu com a cobrança: você não reconhece, foi cobrada duas vezes, o valor está errado, não recebeu a compra, ou o cartão foi roubado?",
		"es-AR": "Quiero asegurarme de entenderte. ¿Qué pasó con el cargo: no lo reconocés, se cobró dos veces, el monto es incorrecto, no recibiste la compra, o te robaron la tarjeta?",
		"es-CO": "Quiero asegurarme de entenderle. ¿Qué pasó con el cargo: no lo reconoce, se cobró dos veces, el monto es incorrecto, no recibió la compra, o le robaron la tarjeta?",
	},
	"clarify_notfound": {
		"es":    "No encontré ese movimiento en tus tarjetas. ¿Me das la fecha aproximada, el monto o el nombre del comercio?",
		"pt":    "Não encontrei essa movimentação nos seus cartões. Pode me dizer a data aproximada, o valor ou o nome do estabelecimento?",
		"es-AR": "No encontré ese movimiento en tus tarjetas. ¿Me pasás la fecha aproximada, el monto o el nombre del comercio?",
		"es-CO": "No encontré ese movimiento en sus tarjetas. ¿Me indica la fecha aproximada, el monto o el nombre del comercio?",
	},
	"clarify_notfound_searched": {
		"es":    "No encontré ningún movimiento{searched} en tus tarjetas. ¿Me confirmas la fecha y el monto, o me dices el nombre del comercio?",
		"pt":    "Não encontrei nenhuma movimentação{searched} nos seus cartões. Pode confirmar a data e o valor, ou me dizer o nome do estabelecimento?",
		"es-AR": "No encontré ningún movimiento{searched} en tus tarjetas. ¿Me confirmás la fecha y el monto, o me decís el nombre del comercio?",
		"es-CO": "No encontré ningún movimiento{searched} en sus tarjetas. ¿Me confirma la fecha y el monto, o me indica el nombre del comercio?",
	},
	"clarify_multi": {
		"es":    "Encontré {count} movimientos que podrían ser. ¿Cuál es el que quieres disputar?",
		"pt":    "Encontrei {count} movimentações que podem ser. Qual delas você quer contestar?",
		"es-AR": "Encontré {count} movimientos que podrían ser. ¿Cuál es el que querés disputar?",
		"es-CO": "Encontré {count} movimientos que podrían ser. ¿Cuál es el que quiere disputar?",
	},
	"confirm_open_case": {
		"es":    "Encontré el cargo de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4}. ¿Confirmas que abra una disputa por \"{type}\"?",
		"pt":    "Encontrei a cobrança de {amount} em {merchant} de {date} no seu cartão final {last4}. Confirma que eu abra uma contestação por \"{type}\"?",
		"es-AR": "Encontré el cargo de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4}. ¿Confirmás que abra una disputa por \"{type}\"?",
		"es-CO": "Encontré el cargo de {amount} en {merchant} del {date} con su tarjeta terminada en {last4}. ¿Confirma que abra una disputa por \"{type}\"?",
	},
	"confirm_block_card": {
		"es":    "Por tu seguridad, te recomiendo bloquear la tarjeta terminada en {last4} y pasar tu caso a un especialista. Para bloquearla te pediré un código de verificación. ¿Confirmas el bloqueo?",
		"pt":    "Para sua segurança, recomendo bloquear o cartão final {last4} e encaminhar seu caso a um especialista. Para bloquear, vou pedir um código de verificação. Confirma o bloqueio?",
		"es-AR": "Por tu seguridad, te recomiendo bloquear la tarjeta terminada en {last4} y pasar tu caso a un especialista. Para bloquearla te voy a pedir un código de verificación. ¿Confirmás el bloqueo?",
		"es-CO": "Por su seguridad, le recomiendo bloquear la tarjeta terminada en {last4} y pasar su caso a un especialista. Para bloquearla le pediré un código de verificación. ¿Confirma el bloqueo?",
	},
	"case_opened": {
		"es":    "Listo: abrí la disputa {case_id} por el cargo de {amount} en {merchant}. Verifiqué que el caso quedó registrado. Te avisaremos por la app cuando haya novedades.",
		"pt":    "Pronto: abri a contestação {case_id} da cobrança de {amount} em {merchant}. Verifiquei que o caso ficou registrado. Avisaremos pelo app quando houver novidades.",
		"es-AR": "Listo: abrí la disputa {case_id} por el cargo de {amount} en {merchant}. Verifiqué que el caso quedó registrado. Te vamos a avisar por la app cuando haya novedades.",
		"es-CO": "Listo: abrí la disputa {case_id} por el cargo de {amount} en {merchant}. Verifiqué que el caso quedó registrado. Le avisaremos por la app cuando haya novedades.",
	},
	"case_exists": {
		"es":    "Ese cargo de {amount} en {merchant} ya tiene la disputa {case_id} abierta, así que no abrí otra. Te avisaremos por la app cuando haya novedades.",
		"pt":    "Essa cobrança de {amount} em {merchant} já tem a contestação {case_id} aberta, então não abri outra. Avisaremos pelo app quando houver novidades.",
		"es-AR": "Ese cargo de {amount} en {merchant} ya tiene la disputa {case_id} abierta, así que no abrí otra. Te vamos a avisar por la app cuando haya novedades.",
		"es-CO": "Ese cargo de {amount} en {merchant} ya tiene la disputa {case_id} abierta, así que no abrí otra. Le avisaremos por la app cuando haya novedades.",
	},
	"explain_reversed": {
		"es":    "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4} ya fue revertido, así que el dinero volvió a tu cuenta y no hace falta abrir una disputa. Si ves algo distinto en tu estado de cuenta, escríbeme.",
		"pt":    "Verifiquei essa movimentação: a cobrança de {amount} em {merchant} de {date} no seu cartão final {last4} já foi estornada, então o dinheiro voltou para a sua conta e não é preciso abrir uma contestação. Se você vir algo diferente na sua fatura, me escreva.",
		"es-AR": "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4} ya fue revertido, así que la plata volvió a tu cuenta y no hace falta abrir una disputa. Si ves algo distinto en tu resumen, escribime.",
		"es-CO": "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} con su tarjeta terminada en {last4} ya fue revertido, así que el dinero volvió a su cuenta y no hace falta abrir una disputa. Si ve algo distinto en su extracto, escríbame.",
	},
	"explain_declined": {
		"es":    "Revisé ese movimiento: la compra de {amount} en {merchant} del {date} con tu tarjeta terminada en {last4} fue rechazada, así que no se te cobró nada y no hay nada que disputar.",
		"pt":    "Verifiquei essa movimentação: a compra de {amount} em {merchant} de {date} no seu cartão final {last4} foi recusada, então nada foi cobrado e não há o que contestar.",
		"es-CO": "Revisé ese movimiento: la compra de {amount} en {merchant} del {date} con su tarjeta terminada en {last4} fue rechazada, así que no se le cobró nada y no hay nada que disputar.",
	},
	"explain_pending": {
		"es":    "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} todavía está pendiente, es decir, el comercio aún no lo confirma y puede cambiar o desaparecer. Si cuando se confirme sigue estando mal, escríbeme y abrimos la disputa.",
		"pt":    "Verifiquei essa movimentação: a cobrança de {amount} em {merchant} de {date} ainda está pendente, ou seja, o estabelecimento ainda não a confirmou e ela pode mudar ou sumir. Se, quando for confirmada, continuar errada, me escreva e abrimos a contestação.",
		"es-AR": "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} todavía está pendiente, es decir, el comercio aún no lo confirma y puede cambiar o desaparecer. Si cuando se confirme sigue estando mal, escribime y abrimos la disputa.",
		"es-CO": "Revisé ese movimiento: el cargo de {amount} en {merchant} del {date} todavía está pendiente, es decir, el comercio aún no lo confirma y puede cambiar o desaparecer. Si cuando se confirme sigue estando mal, escríbame y abrimos la disputa.",
	},
	"confirm_block_declined": {
		"es":    "Revisé ese movimiento: la compra de {amount} en {merchant} del {date} fue rechazada, así que no se te cobró nada. Pero si no fuiste tú, alguien pudo intentar usar tu tarjeta terminada en {last4}. Te recomiendo bloquearla y pasar el caso al equipo de fraude; para bloquearla te pediré un código de verificación. ¿Confirmas el bloqueo?",
		"pt":    "Verifiquei essa movimentação: a compra de {amount} em {merchant} de {date} foi recusada, então nada foi cobrado. Mas, se não foi você, alguém pode ter tentado usar seu cartão final {last4}. Recomendo bloqueá-lo e encaminhar o caso à equipe de fraude; para bloquear, vou pedir um código de verificação. Confirma o bloqueio?",
		"es-AR": "Revisé ese movimiento: la compra de {amount} en {merchant} del {date} fue rechazada, así que no se te cobró nada. Pero si no fuiste vos, alguien pudo intentar usar tu tarjeta terminada en {last4}. Te recomiendo bloquearla y pasar el caso al equipo de fraude; para bloquearla te voy a pedir un código de verificación. ¿Confirmás el bloqueo?",
		"es-CO": "Revisé ese movimiento: la compra de {amount} en {merchant} del {date} fue rechazada, así que no se le cobró nada. Pero si no fue usted, alguien pudo intentar usar su tarjeta terminada en {last4}. Le recomiendo bloquearla y pasar el caso al equipo de fraude; para bloquearla le pediré un código de verificación. ¿Confirma el bloqueo?",
	},
	"card_blocked_handoff": {
		"es":    "Bloqueé tu tarjeta terminada en {last4} (referencia {block_id}) y verifiqué el bloqueo. Un especialista de NiceBank ya tiene tu caso con todos los datos y te contactará.",
		"pt":    "Bloqueei seu cartão final {last4} (referência {block_id}) e verifiquei o bloqueio. Um especialista da NiceBank já está com seu caso e todos os dados, e entrará em contato.",
		"es-AR": "Bloqueé tu tarjeta terminada en {last4} (referencia {block_id}) y verifiqué el bloqueo. Un especialista de NiceBank ya tiene tu caso con todos los datos y se va a contactar con vos.",
		"es-CO": "Bloqueé su tarjeta terminada en {last4} (referencia {block_id}) y verifiqué el bloqueo. Un especialista de NiceBank ya tiene su caso con todos los datos y se comunicará con usted.",
	},
	"handoff_created": {
		"es":    "Tu caso necesita revisión de un especialista. Ya le pasé los datos verificados y te contactará pronto; no hace falta que repitas la información.",
		"pt":    "Seu caso precisa da análise de um especialista. Já repassei os dados verificados e ele entrará em contato em breve; você não precisa repetir as informações.",
		"es-AR": "Tu caso necesita la revisión de un especialista. Ya le pasé los datos verificados y se va a contactar con vos pronto; no hace falta que repitas la información.",
		"es-CO": "Su caso necesita la revisión de un especialista. Ya le pasé los datos verificados y se comunicará con usted pronto; no hace falta que repita la información.",
	},
	"declined": {
		"es":    "Entendido, no hice ningún cambio. Si quieres retomarlo, escríbeme.",
		"pt":    "Entendido, não fiz nenhuma alteração. Se quiser retomar, é só me escrever.",
		"es-AR": "Entendido, no hice ningún cambio. Si querés retomarlo, escribime.",
		"es-CO": "Entendido, no hice ningún cambio. Si quiere retomarlo, escríbame.",
	},
	"declined_handoff": {
		"es":    "Entendido, no bloqueé la tarjeta. Igual pasé tu caso a un especialista, que te contactará pronto.",
		"pt":    "Entendido, não bloqueei o cartão. Mesmo assim encaminhei seu caso a um especialista, que entrará em contato em breve.",
		"es-AR": "Entendido, no bloqueé la tarjeta. Igual pasé tu caso a un especialista, que se va a contactar con vos pronto.",
		"es-CO": "Entendido, no bloqueé la tarjeta. Igual pasé su caso a un especialista, que se comunicará con usted pronto.",
	},
	"tech_failure": {
		"es":    "Tengo un problema técnico para revisar tu caso ahora. Para no dejarte sin respuesta, lo pasé a un especialista que te contactará.",
		"pt":    "Estou com um problema técnico para analisar seu caso agora. Para não deixar você sem resposta, encaminhei a um especialista que entrará em contato.",
		"es-AR": "Tengo un problema técnico para revisar tu caso ahora. Para no dejarte sin respuesta, lo pasé a un especialista que se va a contactar con vos.",
		"es-CO": "Tengo un problema técnico para revisar su caso ahora. Para que no quede sin respuesta, lo pasé a un especialista que se comunicará con usted.",
	},
	"action_failed": {
		"es":    "No pude confirmar que la acción se completó, así que no la doy por hecha. Pasé tu caso a un especialista.",
		"pt":    "Não consegui confirmar que a ação foi concluída, então não a considero feita. Encaminhei seu caso a um especialista.",
		"es-CO": "No pude confirmar que la acción se completó, así que no la doy por hecha. Pasé su caso a un especialista.",
	},
}
