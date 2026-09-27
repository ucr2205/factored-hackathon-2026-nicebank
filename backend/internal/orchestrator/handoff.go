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
	"possible_fraud_high_amount": {"¿El cliente conserva la tarjeta física?", "¿Hay otros movimientos que no reconoce?", "¿Se debe emitir una tarjeta de reposición?"},
	"card_lost_or_stolen":        {"¿Cuándo y dónde perdió la tarjeta?", "¿Hubo movimientos después de la pérdida?", "Confirmar dirección de entrega de la tarjeta nueva."},
	"outside_automatic_window":   {"¿Por qué se reporta fuera del plazo automático?", "¿El cliente tiene comprobantes o comunicación con el comercio?"},
	"could_not_identify_transaction": {"¿Qué movimiento quiere disputar el cliente (fecha, monto, comercio)?"},
	"technical_failure":          {"Repetir el paso que falló y confirmar el resultado con el cliente."},
	"action_not_verified":        {"Verificar manualmente si la acción quedó aplicada antes de informar al cliente."},
	"high_amount_duplicate":      {"¿El comercio ya emitió un reverso?", "¿El cliente tiene el comprobante de ambos cobros?"},
	"high_amount_dispute":        {"¿El cliente tiene comprobante o comunicación con el comercio?"},
}

var priorities = map[string]string{"possible_fraud_high_amount": "high", "card_lost_or_stolen": "high"}

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
		if usd, fx, err := tools.AmountUSD(t.ctx, t.tx, *txn); err == nil {
			h.VerifiedFacts = append(h.VerifiedFacts, contract.Fact{Fact: fmt.Sprintf("Monto en USD: %.2f (%s)", usd, fx), Source: "exchange_rates"})
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
		"amount": money(txn.Amount, txn.Currency, t.lang), "merchant": orDash(txn.Merchant),
		"date": date(txn.Date, t.lang), "last4": txn.CardLast4, "brand": txn.CardBrand, "type": name,
	}
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

func orDash(s string) string {
	if s == "" {
		return "—"
	}
	return s
}
