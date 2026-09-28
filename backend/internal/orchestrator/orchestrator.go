// Package orchestrator runs each chat turn as a deterministic state machine:
// Understand -> Decide -> Act (only after customer confirmation) -> Verify -> Respond or Escalate.
// The language model proposes (extraction, wording); this package decides, calls tools and audits every step.
package orchestrator

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"slices"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"

	"github.com/factored-hackathon-2026/disputes/backend/internal/audit"
	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/guard"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/mlclient"
	"github.com/factored-hackathon-2026/disputes/backend/internal/notify"
	"github.com/factored-hackathon-2026/disputes/backend/internal/pii"
	"github.com/factored-hackathon-2026/disputes/backend/internal/policy"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
	"github.com/factored-hackathon-2026/disputes/backend/internal/tools"
)

var (
	ErrSessionExpired = errors.New("session expired")
	ErrStepUpRequired = errors.New("step-up authentication required")
	ErrNotFound       = errors.New("not found")
	ErrBadRequest     = errors.New("bad request")
)

const (
	stageNone              = ""
	stageAwaitingCandidate = "awaiting_candidate"
	stageAwaitingConfirm   = "awaiting_confirm"
	stageClosed            = "closed"
	searchWindowDays       = 30  // no date, amount or merchant: recent movements only
	wideSearchDays         = 400 // amount or merchant without a date: the whole loaded history
	maxMessageBytes        = 2000
)

type Orchestrator struct {
	Store  *store.Store
	Policy *policy.Policy
	ML     *mlclient.Client
	LLM    llm.Provider
	Today  time.Time
	Idle   time.Duration
	PII    *pii.Cipher // decrypts customer_identity; nil disables names (masking falls back to patterns)
	tracer trace.Tracer
}

func New(s *store.Store, p *policy.Policy, ml *mlclient.Client, model llm.Provider, today time.Time, idle time.Duration) *Orchestrator {
	return &Orchestrator{Store: s, Policy: p, ML: ml, LLM: model, Today: today, Idle: idle,
		tracer: otel.Tracer("disputes/orchestrator")}
}

// state is persisted per session in chat_sessions.state.
type state struct {
	Stage          string         `json:"stage"`
	DisputeType    string         `json:"dispute_type,omitempty"`
	Clarifications int            `json:"clarifications"`
	Extraction     llm.Extraction `json:"extraction"`
	CandidateIDs   []string       `json:"candidate_ids,omitempty"`
	SelectedTxn    string         `json:"selected_txn,omitempty"`
	PendingAction  string         `json:"pending_action,omitempty"`
	FirstMessage   string         `json:"first_message,omitempty"` // masked
	RuleIDs        []string       `json:"rule_ids,omitempty"`
}

type session struct {
	ID    string
	Lang  string
	State state
}

// actionPayload is stored with a pending action; it is everything needed to execute it later.
type actionPayload struct {
	TransactionID string  `json:"transaction_id,omitempty"`
	DisputeType   string  `json:"dispute_type"`
	ProductID     string  `json:"product_id,omitempty"`
	CardLast4     string  `json:"card_last4,omitempty"`
	CardBrand     string  `json:"card_brand,omitempty"`
	RuleID        string  `json:"rule_id"`
	Reason        string  `json:"reason,omitempty"`
	Queue         string  `json:"queue,omitempty"`
	AmountUSD     float64 `json:"amount_usd,omitempty"`
	ThenHandoff   bool    `json:"then_handoff,omitempty"`
}

// turn carries one request through the state machine inside a customer-scoped transaction.
type turn struct {
	o        *Orchestrator
	ctx      context.Context
	tx       pgx.Tx
	p        auth.Principal
	s        *session
	lang     string
	mode     string
	traceID  string
	out      contract.ChatTurn
	usage    llm.Usage
	names    []string
	notified []string // notification kinds queued in this turn
}

// HandleMessage processes one customer message. mode is "system" or "baseline".
func (o *Orchestrator) HandleMessage(ctx context.Context, p auth.Principal, req contract.ChatRequest, mode string) (contract.ChatTurn, error) {
	start := time.Now()
	lang := normLang(req.Lang)
	msg := strings.TrimSpace(req.Message)
	if msg == "" && req.SelectTransactionID == nil {
		return contract.ChatTurn{}, ErrBadRequest
	}
	if len(msg) > maxMessageBytes {
		msg = strings.ToValidUTF8(msg[:maxMessageBytes], "")
	}
	ctx, span := o.tracer.Start(ctx, "chat.turn", trace.WithAttributes(
		attribute.String("chat.mode", mode), attribute.String("chat.lang", lang)))
	defer span.End()

	var out contract.ChatTurn
	err := o.Store.WithCustomer(ctx, p.CustomerRef, func(tx pgx.Tx) error {
		s, err := o.loadOrCreate(ctx, tx, req.SessionID, lang)
		if err != nil {
			return err
		}
		t := o.newTurn(ctx, tx, p, s, lang, mode, span)
		if msg != "" {
			if err := t.saveMessage("customer", msg); err != nil {
				return err
			}
		}
		if mode == "baseline" {
			err = t.baseline(msg)
		} else {
			err = t.system(msg, req.SelectTransactionID)
		}
		if err != nil {
			return err
		}
		out, err = t.finish(start)
		return err
	})
	o.record(span, out, mode, lang, start, err)
	return out, err
}

// Confirm executes (or cancels) a pending action after the customer's explicit decision.
func (o *Orchestrator) Confirm(ctx context.Context, p auth.Principal, req contract.ConfirmRequest) (contract.ChatTurn, error) {
	start := time.Now()
	ctx, span := o.tracer.Start(ctx, "chat.confirm")
	defer span.End()

	var out contract.ChatTurn
	var lang string
	err := o.Store.WithCustomer(ctx, p.CustomerRef, func(tx pgx.Tx) error {
		s, err := o.loadOrCreate(ctx, tx, &req.SessionID, "")
		if err != nil {
			return err
		}
		lang = s.Lang
		var actionType string
		var raw []byte
		// FOR UPDATE serializes concurrent confirms: the second one waits, re-checks status and finds nothing.
		err = tx.QueryRow(ctx, `SELECT action_type, payload FROM pending_actions
			WHERE action_id = $1 AND session_id = $2 AND status = 'pending' FOR UPDATE`, req.ActionID, s.ID).Scan(&actionType, &raw)
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrNotFound
		} else if err != nil {
			return err
		}
		var pl actionPayload
		if err := json.Unmarshal(raw, &pl); err != nil {
			return err
		}
		// Step-up is enforced here, in the service layer, before anything is written.
		if req.Confirm && o.Policy.RequiresStepUp(actionType) && p.ACR < 2 {
			return ErrStepUpRequired
		}
		t := o.newTurn(ctx, tx, p, s, s.Lang, "system", span)
		if err := t.decide(req.ActionID, actionType, pl, req.Confirm); err != nil {
			return err
		}
		out, err = t.finish(start)
		return err
	})
	o.record(span, out, "system", lang, start, err)
	return out, err
}

func (o *Orchestrator) newTurn(ctx context.Context, tx pgx.Tx, p auth.Principal, s *session, lang, mode string, span trace.Span) *turn {
	t := &turn{o: o, ctx: ctx, tx: tx, p: p, s: s, lang: lang, mode: mode, traceID: span.SpanContext().TraceID().String()}
	t.out = contract.ChatTurn{SessionID: s.ID, ActionsVerified: []contract.VerifiedAction{}, RuleIDs: []string{}, Mode: mode}
	// Names are decrypted only in memory, to mask them in the customer's text before it reaches any model.
	if first, last, err := o.customerNames(ctx, tx); err == nil {
		t.names = strings.Fields(first + " " + last)
	} else {
		telemetry.PIIMaskDegraded.Inc()
		t.audit("understand", "pii", "customer names unavailable; masking falls back to patterns only", "degraded", "", 0)
	}
	return t
}

func (o *Orchestrator) record(span trace.Span, out contract.ChatTurn, mode, lang string, start time.Time, err error) {
	if err != nil {
		span.SetStatus(codes.Error, err.Error())
		return
	}
	span.SetAttributes(attribute.String("chat.outcome", out.Outcome), attribute.StringSlice("policy.rule_ids", out.RuleIDs))
	telemetry.ChatTurns.WithLabelValues(lang, out.Outcome, mode).Inc()
	telemetry.TurnDuration.WithLabelValues(mode).Observe(time.Since(start).Seconds())
}

func (o *Orchestrator) loadOrCreate(ctx context.Context, tx pgx.Tx, id *string, lang string) (*session, error) {
	s := &session{}
	if id == nil || *id == "" {
		if lang == "" {
			lang = "es"
		}
		err := tx.QueryRow(ctx, `INSERT INTO chat_sessions (lang) VALUES ($1) RETURNING session_id`, lang).Scan(&s.ID)
		s.Lang = lang
		return s, err
	}
	var raw []byte
	var last time.Time
	var closed *time.Time
	err := tx.QueryRow(ctx, `SELECT session_id, lang, state, last_activity_at, closed_at FROM chat_sessions WHERE session_id = $1`,
		*id).Scan(&s.ID, &s.Lang, &raw, &last, &closed)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound // also what RLS returns for another customer's session
	} else if err != nil {
		return nil, err
	}
	if closed != nil || time.Since(last) > o.Idle {
		return nil, ErrSessionExpired
	}
	if lang != "" {
		s.Lang = lang
	}
	_ = json.Unmarshal(raw, &s.State)
	if s.State.Stage == stageClosed { // a new dispute in the same conversation starts from a clean state
		s.State = state{}
	}
	return s, nil
}

// ---------- the system path ----------

func (t *turn) system(msg string, selected *string) error {
	st := &t.s.State
	if selected != nil && *selected != "" {
		if st.Stage != stageAwaitingCandidate || !slices.Contains(st.CandidateIDs, *selected) {
			return ErrBadRequest
		}
		return t.evaluate(*selected)
	}

	masked := guard.Mask(msg, t.names...)
	if guard.LooksLikeInjection(msg) {
		t.audit("understand", "guard", "instruction-override or forbidden-action pattern in customer text", "blocked", "SEC-INJ-01", 0)
		return t.reply("abstain", "abstain_injection", nil, "SEC-INJ-01")
	}

	switch st.Stage {
	case stageAwaitingCandidate:
		merchants := make([]string, len(st.CandidateIDs))
		for i, id := range st.CandidateIDs {
			if txn, err := tools.GetTransaction(t.ctx, t.tx, id); err == nil {
				merchants[i] = txn.Merchant
			}
		}
		idx, u, _ := t.o.LLM.PickCandidate(t.ctx, masked, merchants)
		t.addUsage(u)
		if idx >= 0 {
			t.audit("understand", t.o.LLM.Name(), fmt.Sprintf("customer picked candidate %d of %d", idx+1, len(merchants)), "selected", "", 0)
			return t.evaluate(st.CandidateIDs[idx])
		}
	case stageAwaitingConfirm:
		return t.repeatPending()
	}

	// Extraction starts now and runs while the classifier decides whether this message is a dispute at all.
	waitExtraction, discardExtraction := t.startExtraction(masked)
	extracted := false
	defer func() {
		if !extracted {
			discardExtraction()
		}
	}()

	// Understand: classify the dispute type with the learned component (ml-service).
	began := time.Now()
	cls, err := t.o.ML.Classify(t.ctx, masked, t.lang)
	if err != nil {
		t.audit("understand", "ml-service", "classification failed after bounded retries", "error", "ESC-TECH-01", time.Since(began))
		return t.escalate("technical_failure", "ESC-TECH-01", "tech_failure", nil, "disputes", nil)
	}
	t.audit("understand", "ml-service", fmt.Sprintf("label=%s confidence=%.2f abstain=%t model=%s", cls.Label, cls.Confidence, cls.Abstain, cls.ModelVersion),
		cls.Label, "", time.Since(began))

	if cls.Label == "out_of_scope" && st.DisputeType == "" {
		return t.reply("abstain", "abstain_scope", nil, "SCOPE-01")
	}
	if _, known := t.o.Policy.Type(cls.Label); known && !cls.Abstain {
		st.DisputeType = cls.Label
	}
	if st.DisputeType == "" {
		return t.clarify("clarify_type", "CLARIFY-TYPE")
	}
	if st.FirstMessage == "" {
		st.FirstMessage = masked
	}
	if st.DisputeType == "card_lost_stolen" {
		dec, _ := t.o.Policy.Evaluate(policy.Facts{DisputeType: st.DisputeType})
		t.audit("policy", "policy", "type=card_lost_stolen", string(dec.Kind), dec.RuleID, 0)
		return t.proposeBlock(nil, dec)
	}

	// Understand: extract facts (the model proposes; nothing is trusted until matched against records).
	extracted = true
	r := waitExtraction()
	ex, u := r.ex, r.u
	t.addUsage(u)
	st.Extraction = st.Extraction.Merge(ex)
	t.audit("extract", t.o.LLM.Name(), describeExtraction(st.Extraction), "", "", 0)

	// Decide: find matching card transactions for this customer.
	cands, err := t.findCandidates()
	if err != nil {
		return err
	}
	t.audit("find_transactions", "find_transactions", fmt.Sprintf("%d candidate(s) for type=%s", len(cands), st.DisputeType), fmt.Sprint(len(cands)), "", 0)
	telemetry.ToolCalls.WithLabelValues("find_transactions", "ok").Inc()

	switch len(cands) {
	case 0:
		if searched := t.searchedFacts(); searched != "" {
			return t.clarifyWith("clarify_notfound_searched", "CLARIFY-NOTFOUND", map[string]string{"searched": searched})
		}
		return t.clarify("clarify_notfound", "CLARIFY-NOTFOUND")
	case 1:
		return t.evaluate(cands[0].ID)
	default:
		st.Stage = stageAwaitingCandidate
		st.CandidateIDs = nil
		for _, c := range cands {
			st.CandidateIDs = append(st.CandidateIDs, c.ID)
			t.out.Candidates = append(t.out.Candidates, contract.Candidate{TransactionID: c.ID, Date: c.Date, Amount: c.Amount,
				Currency: c.Currency, Merchant: c.Merchant, City: c.City, Country: c.Country, CardLast4: c.CardLast4})
		}
		return t.reply("clarify", "clarify_multi", map[string]string{"count": fmt.Sprint(len(cands))}, "CLARIFY-MULTI")
	}
}

func (t *turn) findCandidates() ([]tools.Transaction, error) {
	st := &t.s.State
	to := t.o.Today
	from := to.AddDate(0, 0, -searchWindowDays)
	if st.Extraction.Amount != nil || st.Extraction.MerchantHint != "" {
		from = to.AddDate(0, 0, -wideSearchDays)
	}
	if st.Extraction.DateFrom != nil {
		from, to = *st.Extraction.DateFrom, *st.Extraction.DateTo
	}
	limit := t.o.Policy.Globals.MaxCandidatesShown
	if st.DisputeType == "duplicate_charge" {
		return tools.FindDuplicates(t.ctx, t.tx, from, to, limit)
	}
	types := []string{"Purchase", "Withdrawal"}
	if st.DisputeType == "atm_cash_not_dispensed" {
		types = []string{"Withdrawal"}
	}
	return tools.FindTransactions(t.ctx, t.tx, tools.Filter{From: from, To: to, Amount: st.Extraction.Amount,
		MerchantHint: st.Extraction.MerchantHint, Types: types}, limit)
}

// evaluate applies the policy to one identified transaction and proposes the next action.
func (t *turn) evaluate(txnID string) error {
	st := &t.s.State
	txn, err := tools.GetTransaction(t.ctx, t.tx, txnID)
	if errors.Is(err, pgx.ErrNoRows) {
		return t.clarify("clarify_notfound", "CLARIFY-NOTFOUND")
	} else if err != nil {
		return err
	}
	st.SelectedTxn, st.Stage, st.CandidateIDs = txn.ID, stageNone, nil

	// One open case per transaction: report the existing one instead of opening a duplicate.
	if caseID, found, err := tools.OpenCaseFor(t.ctx, t.tx, txn.ID); err != nil {
		return err
	} else if found {
		t.audit("policy", "dispute_cases", "transaction already has open case "+caseID, "existing_case", "DISP-DUPCASE-01", 0)
		st.Stage = stageClosed
		t.out.CaseID = &caseID
		facts := t.txnFacts(txn)
		facts["case_id"] = caseID
		return t.reply("resolve", "case_exists", facts, "DISP-DUPCASE-01")
	}

	usd, fx, err := tools.AmountUSD(t.ctx, t.tx, txn)
	if err != nil {
		t.audit("policy", "exchange_rates", err.Error(), "error", "ESC-TECH-01", 0)
		return t.escalate("technical_failure", "ESC-TECH-01", "tech_failure", &txn, "disputes", nil)
	}
	age := int(t.o.Today.Sub(txn.Date).Hours() / 24)
	dec, err := t.o.Policy.Evaluate(policy.Facts{DisputeType: st.DisputeType, AgeDays: age, Status: txn.Status, AmountUSD: usd})
	if err != nil {
		return err
	}
	t.audit("policy", "policy", fmt.Sprintf("type=%s txn=%s age_days=%d status=%s amount_usd=%.2f fx=%s",
		st.DisputeType, txn.ID, age, txn.Status, usd, fx), string(dec.Kind), dec.RuleID, 0)

	switch dec.Kind {
	case policy.Auto:
		pl := actionPayload{TransactionID: txn.ID, DisputeType: st.DisputeType, RuleID: dec.RuleID, AmountUSD: usd}
		facts := t.txnFacts(txn)
		return t.propose("open_dispute_case", pl, "confirm_open_case", facts, dec.RuleID)
	case policy.Escalate:
		if dec.SuggestAction == "block_card" {
			return t.proposeBlock(&txn, dec)
		}
		return t.escalate(dec.Reason, dec.RuleID, "handoff_created", &txn, dec.Queue, nil)
	default:
		return t.escalate(dec.Reason, dec.RuleID, "handoff_created", &txn, dec.Queue, nil)
	}
}

func (t *turn) proposeBlock(txn *tools.Transaction, dec policy.Decision) error {
	cards, err := tools.ActiveCards(t.ctx, t.tx)
	if err != nil {
		return err
	}
	var card *tools.Card
	for i := range cards {
		if cards[i].Status == "Active" && (txn == nil || cards[i].ProductID == txn.ProductID) {
			card = &cards[i]
			break
		}
	}
	if card == nil { // nothing to block: go straight to a human
		return t.escalate(dec.Reason, dec.RuleID, "handoff_created", txn, dec.Queue, nil)
	}
	pl := actionPayload{DisputeType: t.s.State.DisputeType, ProductID: card.ProductID, CardLast4: card.Last4, CardBrand: card.Brand,
		RuleID: dec.RuleID, Reason: dec.Reason, Queue: dec.Queue, ThenHandoff: true}
	if txn != nil {
		pl.TransactionID = txn.ID
	}
	return t.propose("block_card", pl, "confirm_block_card", map[string]string{"last4": card.Last4}, dec.RuleID)
}

// propose stores a pending action; nothing is executed until the customer confirms.
func (t *turn) propose(actionType string, pl actionPayload, intent string, facts map[string]string, ruleID string) error {
	raw, _ := json.Marshal(pl)
	var id string
	if err := t.tx.QueryRow(t.ctx, `INSERT INTO pending_actions (session_id, action_type, payload)
		VALUES ($1, $2, $3) RETURNING action_id`, t.s.ID, actionType, raw).Scan(&id); err != nil {
		return err
	}
	t.s.State.Stage, t.s.State.PendingAction = stageAwaitingConfirm, id
	t.audit("propose", actionType, fmt.Sprintf("pending action %s awaiting customer confirmation", actionType), "pending", ruleID, 0)
	if err := t.reply("confirm", intent, facts, ruleID); err != nil {
		return err
	}
	t.out.PendingAction = &contract.PendingAction{ID: id, Type: actionType, Summary: t.out.Reply,
		RequiresStepUp: t.o.Policy.RequiresStepUp(actionType)}
	return nil
}

func (t *turn) repeatPending() error {
	var actionType string
	var raw []byte
	err := t.tx.QueryRow(t.ctx, `SELECT action_type, payload FROM pending_actions WHERE action_id = $1 AND status = 'pending'`,
		t.s.State.PendingAction).Scan(&actionType, &raw)
	if err != nil {
		t.s.State = state{}
		return t.clarify("clarify_type", "CLARIFY-TYPE")
	}
	var pl actionPayload
	_ = json.Unmarshal(raw, &pl)
	intent, facts := "confirm_block_card", map[string]string{"last4": pl.CardLast4}
	if actionType == "open_dispute_case" {
		txn, err := tools.GetTransaction(t.ctx, t.tx, pl.TransactionID)
		if err != nil {
			return err
		}
		intent, facts = "confirm_open_case", t.txnFacts(txn)
	}
	if err := t.reply("confirm", intent, facts, pl.RuleID); err != nil {
		return err
	}
	t.out.PendingAction = &contract.PendingAction{ID: t.s.State.PendingAction, Type: actionType, Summary: t.out.Reply,
		RequiresStepUp: t.o.Policy.RequiresStepUp(actionType)}
	return nil
}

// decide runs after an explicit confirm/cancel: Act -> Verify -> Respond or Escalate.
func (t *turn) decide(actionID, actionType string, pl actionPayload, confirm bool) error {
	t.s.State.DisputeType = pl.DisputeType
	var txn *tools.Transaction
	if pl.TransactionID != "" {
		if got, err := tools.GetTransaction(t.ctx, t.tx, pl.TransactionID); err == nil {
			txn = &got
		}
	}
	if !confirm {
		_, _ = t.tx.Exec(t.ctx, `UPDATE pending_actions SET status = 'cancelled', decided_at = now() WHERE action_id = $1`, actionID)
		t.audit("confirm", actionType, "customer declined the proposed action", "cancelled", pl.RuleID, 0)
		if pl.ThenHandoff {
			return t.escalate(pl.Reason, pl.RuleID, "declined_handoff", txn, pl.Queue, nil)
		}
		t.s.State.Stage = stageClosed
		return t.reply("abstain", "declined", nil, "")
	}
	t.audit("confirm", actionType, "customer confirmed the proposed action", "confirmed", pl.RuleID, 0)

	began := time.Now()
	switch actionType {
	case "open_dispute_case":
		desc := fmt.Sprintf("%s reported via assistant: %s", pl.DisputeType, t.s.State.FirstMessage)
		v, err := tools.OpenDisputeCase(t.ctx, t.tx, pl.TransactionID, pl.DisputeType, desc, actionID)
		if err != nil {
			return t.actionFailed(actionID, actionType, pl, txn, err)
		}
		t.markExecuted(actionID)
		t.verified(actionType, v, pl.RuleID, time.Since(began))
		t.out.CaseID = &v.Reference
		t.s.State.Stage = stageClosed
		facts := map[string]string{"case_id": v.Reference}
		if txn != nil {
			for k, val := range t.txnFacts(*txn) {
				facts[k] = val
			}
		}
		t.queueNotification(notify.KindCaseOpened, facts)
		return t.reply("resolve", "case_opened", facts, pl.RuleID)
	case "block_card":
		v, err := tools.BlockCard(t.ctx, t.tx, pl.ProductID, pl.Reason)
		if err != nil {
			return t.actionFailed(actionID, actionType, pl, txn, err)
		}
		t.markExecuted(actionID)
		t.verified(actionType, v, pl.RuleID, time.Since(began))
		taken := []contract.ActionTaken{{Action: "block_card", Status: "verified", Reference: v.Reference, At: v.VerifiedAt}}
		t.queueNotification(notify.KindCardBlocked, map[string]string{"last4": pl.CardLast4, "brand": pl.CardBrand, "block_id": v.Reference})
		return t.escalateWithFacts(pl.Reason, pl.RuleID, "card_blocked_handoff", txn, pl.Queue, taken,
			map[string]string{"last4": pl.CardLast4, "block_id": v.Reference})
	}
	return ErrBadRequest
}

func (t *turn) actionFailed(actionID, actionType string, pl actionPayload, txn *tools.Transaction, err error) error {
	_, _ = t.tx.Exec(t.ctx, `UPDATE pending_actions SET status = 'failed', decided_at = now() WHERE action_id = $1`, actionID)
	telemetry.ToolCalls.WithLabelValues(actionType, "not_verified").Inc()
	t.audit("verify", actionType, "action could not be verified: "+err.Error(), "not_verified", "ESC-TECH-01", 0)
	return t.escalate("action_not_verified", "ESC-TECH-01", "action_failed", txn, "disputes", nil)
}

func (t *turn) markExecuted(actionID string) {
	_, _ = t.tx.Exec(t.ctx, `UPDATE pending_actions SET status = 'executed', decided_at = now() WHERE action_id = $1`, actionID)
}

func (t *turn) verified(actionType string, v tools.Verified, ruleID string, took time.Duration) {
	telemetry.ToolCalls.WithLabelValues(actionType, "verified").Inc()
	t.audit("act", actionType, "executed "+actionType+" -> "+v.Reference, "executed", ruleID, took)
	t.audit("verify", actionType, "read back "+v.Reference+" and confirmed the new state", "verified", ruleID, 0)
	t.out.ActionsVerified = append(t.out.ActionsVerified, contract.VerifiedAction{Type: actionType, Reference: v.Reference, VerifiedAt: v.VerifiedAt})
}

func (t *turn) clarify(intent, ruleID string) error { return t.clarifyWith(intent, ruleID, nil) }

// searchedFacts words what was searched ("de 324,48 del 23 de diciembre de 2025"), or "" if nothing was given.
func (t *turn) searchedFacts() string {
	ex, parts := t.s.State.Extraction, []string{}
	if ex.Amount != nil {
		parts = append(parts, "de "+strings.Replace(fmt.Sprintf("%.2f", *ex.Amount), ".", ",", 1))
	}
	if ex.DateFrom != nil && ex.DateTo != nil && ex.DateFrom.Format(time.DateOnly) == ex.DateTo.Format(time.DateOnly) {
		parts = append(parts, map[string]string{"es": "del ", "pt": "de "}[t.lang]+t.dateText(*ex.DateFrom))
	}
	if len(parts) == 0 {
		return ""
	}
	return " " + strings.Join(parts, " ")
}

func (t *turn) clarifyWith(intent, ruleID string, facts map[string]string) error {
	st := &t.s.State
	st.Clarifications++
	if st.Clarifications > t.o.Policy.Globals.MaxClarifications {
		return t.escalate("could_not_identify_transaction", "ESC-CLARIFY-LIMIT", "handoff_created", nil, "disputes", nil)
	}
	return t.reply("clarify", intent, facts, ruleID)
}

// reply composes the customer-facing text from verified facts only.
func (t *turn) reply(outcome, intent string, facts map[string]string, ruleID string) error {
	text, u, err := t.o.LLM.Compose(t.ctx, llm.ComposeInput{Intent: intent, Lang: t.lang, Facts: facts})
	if err != nil {
		return err
	}
	t.addUsage(u)
	t.out.Reply, t.out.Outcome = text, outcome
	if ruleID != "" {
		t.out.RuleIDs = append(t.out.RuleIDs, ruleID)
		t.s.State.RuleIDs = append(t.s.State.RuleIDs, ruleID)
	}
	return nil
}

func (t *turn) addUsage(u llm.Usage) {
	t.usage.InputTokens += u.InputTokens
	t.usage.OutputTokens += u.OutputTokens
	t.usage.CostUSD += u.CostUSD
}

func (t *turn) audit(step, tool, summary, result, ruleID string, took time.Duration) {
	_, span := t.o.tracer.Start(t.ctx, "step."+step, trace.WithAttributes(
		attribute.String("step.tool", tool), attribute.String("step.result", result), attribute.String("policy.rule_id", ruleID)))
	span.End()
	_ = audit.Write(t.ctx, t.tx, audit.Event{SessionID: t.s.ID, Step: step, Tool: tool, Summary: summary,
		Result: result, RuleID: ruleID, TraceID: t.traceID, Latency: took, Lang: t.lang, Mode: t.mode})
}

func (t *turn) saveMessage(role, text string) error {
	_, err := t.tx.Exec(t.ctx, `INSERT INTO messages (session_id, role, text, lang, mode) VALUES ($1, $2, $3, $4, $5)`,
		t.s.ID, role, text, t.lang, t.mode)
	return err
}

func (t *turn) finish(start time.Time) (contract.ChatTurn, error) {
	t.out.TraceID = t.traceID
	t.out.LatencyMS = time.Since(start).Milliseconds()
	t.out.CostUSD = t.usage.CostUSD
	raw, _ := json.Marshal(t.s.State)
	if _, err := t.tx.Exec(t.ctx, `UPDATE chat_sessions SET state = $2, lang = $3, last_activity_at = now() WHERE session_id = $1`,
		t.s.ID, raw, t.lang); err != nil {
		return t.out, err
	}
	if _, err := t.tx.Exec(t.ctx, `INSERT INTO messages (session_id, role, text, outcome, mode, latency_ms, lang)
		VALUES ($1, 'assistant', $2, $3, $4, $5, $6)`, t.s.ID, t.out.Reply, t.out.Outcome, t.mode,
		t.out.LatencyMS, t.lang); err != nil {
		return t.out, err
	}
	last := ""
	if n := len(t.out.RuleIDs); n > 0 {
		last = t.out.RuleIDs[n-1]
	}
	t.audit("respond", "", "turn completed", t.out.Outcome, last, time.Since(start))
	return t.out, nil
}

func normLang(l string) string {
	if l == "pt" {
		return "pt"
	}
	return "es"
}

func describeExtraction(e llm.Extraction) string {
	parts := []string{}
	if e.Amount != nil {
		parts = append(parts, fmt.Sprintf("amount=%.2f", *e.Amount))
	}
	if e.DateFrom != nil {
		parts = append(parts, "date="+e.DateFrom.Format(time.DateOnly)+".."+e.DateTo.Format(time.DateOnly))
	}
	if e.MerchantHint != "" {
		parts = append(parts, "merchant_hint=yes")
	}
	if len(parts) == 0 {
		return "no facts extracted"
	}
	return strings.Join(parts, " ")
}
