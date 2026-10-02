package orchestrator

import (
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/notify"
	"github.com/factored-hackathon-2026/disputes/backend/internal/tools"
)

// Staff-facing text in handoffs is Spanish: the service agents' working language.
var openQuestions = map[string][]string{
	"possible_fraud_high_amount":     {"¿El cliente conserva la tarjeta física?", "¿Hay otros movimientos que no reconoce?", "¿Se debe emitir una tarjeta de reposición?"},
	"card_lost_or_stolen":            {"¿Cuándo y dónde perdió la tarjeta?", "¿Hubo movimientos después de la pérdida?", "Confirmar dirección de entrega de la tarjeta nueva."},
	"outside_automatic_window":       {"¿Por qué se reporta fuera del plazo automático?", "¿El cliente tiene comprobantes o comunicación con el comercio?"},
	"could_not_identify_transaction": {"¿Qué movimiento quiere disputar el cliente (fecha, monto, comercio)?"},
	"technical_failure":              {"Repetir el paso que falló y confirmar el resultado con el cliente."},
	"action_not_verified":            {"Verificar manualmente si la acción quedó aplicada antes de informar al cliente."},
	"high_amount_duplicate":          {"¿El comercio ya emitió un reverso?", "¿El cliente tiene el comprobante de ambos cobros?"},
	"high_amount_dispute":            {"¿El cliente tiene comprobante o comunicación con el comercio?"},
	"declined_unrecognized_attempt":  {"¿Hubo otros intentos rechazados o aprobados que el cliente no reconoce?", "¿Dónde pudo haberse expuesto la tarjeta (compras en línea, pérdida)?", "¿Se debe emitir una tarjeta de reposición?"},
}

var priorities = map[string]string{"possible_fraud_high_amount": "high", "card_lost_or_stolen": "high", "declined_unrecognized_attempt": "high"}

func (t *turn) escalate(reason, ruleID, intent string, txn *tools.Transaction, queue string, taken []contract.ActionTaken) error {
	return t.escalateWithFacts(reason, ruleID, intent, txn, queue, taken, nil)
}

// escalateWithFacts creates the structured handoff (C5), verifies it by reading it back and replies.
func (t *turn) escalateWithFacts(reason, ruleID, intent string, txn *tools.Transaction, queue string, taken []contract.ActionTaken, facts map[string]string) error {
	st := &t.s.State
	if ruleID != "" {
		st.RuleIDs = append(st.RuleIDs, ruleID)
	}
	h := contract.Handoff{
		Language: t.lang, Reason: reason, Priority: "medium", DisputeType: st.DisputeType,
		CustomerRequest: st.FirstMessage, VerifiedFacts: []contract.Fact{}, ActionsTaken: taken,
		OpenQuestions: openQuestions[reason], SuggestedQueue: queue + "_" + t.lang, SessionID: t.s.ID, TraceID: t.traceID,
	}
	if p, ok := priorities[reason]; ok {
		h.Priority = p
	}
	if h.ActionsTaken == nil {
		h.ActionsTaken = []contract.ActionTaken{}
	}
	if h.CustomerRequest == "" {
		h.CustomerRequest = "(sin descripción)"
	}
	if txn != nil {
		h.VerifiedFacts = append(h.VerifiedFacts, contract.Fact{
			Fact: fmt.Sprintf("Movimiento %s: %s en %s el %s (%s), tarjeta terminada en %s, estado %s",
				txn.ID, money(txn.Amount, txn.Currency, "es"), orDash(txn.Merchant), txn.Date.Format("2006-01-02 15:04"),
				orDash(txn.Country), txn.CardLast4, txn.Status),
			Source: "transactions"})
		if c, err := tools.ConvertUSD(t.ctx, t.tx, *txn); err == nil {
			h.VerifiedFacts = append(h.VerifiedFacts, contract.Fact{Fact: staffAmount(*txn, c), Source: "exchange_rates"})
		}
	}
	for _, a := range taken {
		h.VerifiedFacts = append(h.VerifiedFacts, contract.Fact{Fact: fmt.Sprintf("Acción %s aplicada y verificada (%s)", a.Action, a.Reference), Source: "card_blocks"})
	}
	seen := map[string]bool{}
	for _, r := range st.RuleIDs {
		if r != "" && !seen[r] {
			seen[r] = true
			h.Evidence = append(h.Evidence, contract.Evidence{Type: "policy_rule", ID: r})
		}
	}
	if agents, err := tools.SuggestAgents(t.ctx, t.tx, t.lang, queue); err == nil {
		for _, a := range agents {
			h.SuggestedAgents = append(h.SuggestedAgents, contract.SuggestedAgent(a))
		}
	}

	raw, _ := json.Marshal(h)
	var id, status string
	if err := t.tx.QueryRow(t.ctx, `INSERT INTO handoffs (session_id, language, reason, priority, payload)
		VALUES ($1, $2, $3, $4, $5) RETURNING handoff_id, status`, t.s.ID, t.lang, reason, h.Priority, raw).Scan(&id, &status); err != nil {
		return err
	}
	if status != "open" {
		return fmt.Errorf("handoff %s not verified", id)
	}
	t.audit("handoff", "create_handoff", fmt.Sprintf("handoff %s to queue %s (reason %s)", id, h.SuggestedQueue, reason), "verified", ruleID, 0)
	if !t.hasNotified(notify.KindCardBlocked) { // the card-blocked email already says a specialist has the case
		t.queueNotification(notify.KindHandoffCreated, map[string]string{"reference": shortRef(id)})
	}
	t.out.HandoffID = &id
	st.Stage = stageClosed
	if err := t.reply("escalate", intent, facts, ""); err != nil {
		return err
	}
	if ruleID != "" {
		t.out.RuleIDs = append(t.out.RuleIDs, ruleID)
	}
	return nil
}

func (t *turn) txnFacts(txn tools.Transaction) map[string]string {
	name := t.s.State.DisputeType
	if d, ok := t.o.Policy.Type(name); ok {
		name = d.DisplayName[t.lang]
	}
	return map[string]string{
		"amount": t.amountText(txn), "merchant": orDash(txn.Merchant),
		"date": t.dateText(txn.Date), "last4": txn.CardLast4, "brand": txn.CardBrand, "type": name,
	}
}

// amountText is the amount the customer reads: in the card's currency and, when that is not USD, its USD
// equivalent and the rate used, so the figure the policy judged is visible ("1.250.000,00 COP (≈ 316,25 USD;
// tasa del 12 de junio: 1 USD = 3.952,57 COP)"). A missing rate never hides the amount itself.
func (t *turn) amountText(txn tools.Transaction) string {
	base := money(txn.Amount, txn.Currency, t.lang)
	if txn.Currency == "USD" {
		return base
	}
	c, err := tools.ConvertUSD(t.ctx, t.tx, txn)
	if err != nil {
		return base
	}
	approx := "≈ " + money(c.USD, "USD", t.lang)
	if c.Rate <= 0 {
		return fmt.Sprintf("%s (%s)", base, approx)
	}
	label := map[string]string{"es": "tasa del", "pt": "câmbio de"}[t.lang]
	return fmt.Sprintf("%s (%s; %s %s: 1 USD = %s)", base, approx, label, t.dateText(c.RateDate), money(1/c.Rate, txn.Currency, t.lang))
}

// staffAmount is the agent's verified fact: both amounts and the exact rate with its date.
func staffAmount(txn tools.Transaction, c tools.Conversion) string {
	switch {
	case txn.Currency == "USD":
		return fmt.Sprintf("Monto: %s (sin conversión)", money(txn.Amount, "USD", "es"))
	case c.Rate <= 0:
		return fmt.Sprintf("Monto: %s = %s (equivalente del dataset, sin tasa del día)", money(txn.Amount, txn.Currency, "es"), money(c.USD, "USD", "es"))
	}
	return fmt.Sprintf("Monto: %s = %s · tasa 1 USD = %s (1 %s = %s USD) del %s", money(txn.Amount, txn.Currency, "es"),
		money(c.USD, "USD", "es"), money(1/c.Rate, txn.Currency, "es"), txn.Currency,
		strings.Replace(strings.TrimRight(fmt.Sprintf("%.8f", c.Rate), "0"), ".", ",", 1), c.RateDate.Format("02/01/2006"))
}

// money formats 1234.5 as "1.234,50 MXN" (es/pt use dot thousands and comma decimals).
func money(v float64, currency, _ string) string {
	cents := int64(math.Round(v * 100))
	whole, frac := cents/100, cents%100
	s := fmt.Sprint(whole)
	var b strings.Builder
	for i, r := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			b.WriteByte('.')
		}
		b.WriteRune(r)
	}
	return fmt.Sprintf("%s,%02d %s", b.String(), frac, currency)
}

var monthNames = map[string][]string{
	"es": {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"},
	"pt": {"janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"},
}

func date(d time.Time, lang string) string {
	return fmt.Sprintf("%d de %s", d.Day(), monthNames[lang][d.Month()-1])
}

// dateText is date() plus the year when it differs from "today" (the dataset spans several years).
func (t *turn) dateText(d time.Time) string {
	if d.Year() != t.o.Today.Year() {
		return fmt.Sprintf("%s de %d", date(d, t.lang), d.Year())
	}
	return date(d, t.lang)
}

func orDash(s string) string {
	if s == "" {
		return "—"
	}
	return s
}
