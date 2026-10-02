// Package contract holds the JSON shapes of the public API (docs/api/contracts.md).
// Keep in sync with frontend/src/api/types.ts.
//
// Pipeline role: ChatTurn is what every turn returns (reply, outcome, candidates, pending action, verified actions,
// rule ids); Handoff (C5) is what Escalate hands to a human. The remaining types serve the agent console and the
// supervisor view.
package contract

import "time"

// ChatRequest is the body of POST /api/chat: a new message, or the transaction the customer picked from the
// candidates of the previous turn (SelectTransactionID). A nil SessionID starts a new conversation.
type ChatRequest struct {
	SessionID           *string `json:"session_id"`
	Message             string  `json:"message"`
	Lang                string  `json:"lang"`
	SelectTransactionID *string `json:"select_transaction_id"`
}

// ConfirmRequest is the body of POST /api/chat/confirm: the customer's explicit yes/no on a pending action.
type ConfirmRequest struct {
	SessionID string `json:"session_id"`
	ActionID  string `json:"action_id"`
	Confirm   bool   `json:"confirm"`
}

// Candidate is a card transaction from the customer's own history, shown so the customer can pick the charge.
type Candidate struct {
	TransactionID string    `json:"transaction_id"`
	Date          time.Time `json:"date"`
	Amount        float64   `json:"amount"`
	Currency      string    `json:"currency"`
	Merchant      string    `json:"merchant"`
	City          string    `json:"city"`
	Country       string    `json:"country"`
	CardLast4     string    `json:"card_last4"`
}

// PendingAction is an action the system proposed and will only execute after explicit confirmation.
// RequiresStepUp tells the client to ask for a TOTP login (acr >= 2) before confirming.
type PendingAction struct {
	ID             string `json:"id"`
	Type           string `json:"type"`
	Summary        string `json:"summary"`
	RequiresStepUp bool   `json:"requires_step_up"`
}

// VerifiedAction is an executed action whose result was read back from the database.
type VerifiedAction struct {
	Type       string    `json:"type"`
	Reference  string    `json:"reference"`
	VerifiedAt time.Time `json:"verified_at"`
}

// ChatTurn is the response to POST /api/chat and POST /api/chat/confirm: one completed turn of the pipeline.
type ChatTurn struct {
	SessionID       string           `json:"session_id"`
	Reply           string           `json:"reply"`
	Outcome         string           `json:"outcome"` // resolve | clarify | abstain | escalate | confirm
	Candidates      []Candidate      `json:"candidates,omitempty"`
	PendingAction   *PendingAction   `json:"pending_action,omitempty"`
	ActionsVerified []VerifiedAction `json:"actions_verified"`
	CaseID          *string          `json:"case_id"`
	HandoffID       *string          `json:"handoff_id"`
	RuleIDs         []string         `json:"rule_ids"`
	TraceID         string           `json:"trace_id"`
	LatencyMS       int64            `json:"latency_ms"`
	CostUSD         float64          `json:"cost_usd"`
	Mode            string           `json:"mode"`
}

// Message is one stored chat message (role customer or assistant).
type Message struct {
	Role string    `json:"role"`
	Text string    `json:"text"`
	At   time.Time `json:"at"`
}

// SessionView is the response to GET /api/sessions/{id}: the transcript and any pending action, to resume a chat.
type SessionView struct {
	SessionID     string         `json:"session_id"`
	Lang          string         `json:"lang"`
	Messages      []Message      `json:"messages"`
	PendingAction *PendingAction `json:"pending_action,omitempty"`
}

// Fact is a verified statement in a handoff and the table it was read from (transactions, exchange_rates, ...).
type Fact struct {
	Fact   string `json:"fact"`
	Source string `json:"source"`
}

// ActionTaken is an action the assistant already executed and verified before handing off.
type ActionTaken struct {
	Action    string    `json:"action"`
	Status    string    `json:"status"`
	Reference string    `json:"reference"`
	At        time.Time `json:"at"`
}

// Evidence points to a record that supports a handoff, e.g. a policy rule id or a transaction id.
type Evidence struct {
	Type string `json:"type"`
	ID   string `json:"id"`
}

// SuggestedAgent is an active agent who speaks the customer's language, ranked by the queue's specialty.
type SuggestedAgent struct {
	AgentID   string `json:"agent_id"`
	Name      string `json:"name"`
	Languages string `json:"languages"`
	Specialty string `json:"specialty"`
}

// Handoff is contract C5: everything a human agent needs, never the raw transcript.
type Handoff struct {
	HandoffID       string           `json:"handoff_id"`
	CreatedAt       time.Time        `json:"created_at"`
	Status          string           `json:"status"`
	ClaimedBy       *string          `json:"claimed_by,omitempty"`
	Language        string           `json:"language"`
	Reason          string           `json:"reason"`
	Priority        string           `json:"priority"`
	CustomerRequest string           `json:"customer_request"`
	DisputeType     string           `json:"dispute_type"`
	VerifiedFacts   []Fact           `json:"verified_facts"`
	ActionsTaken    []ActionTaken    `json:"actions_taken"`
	Evidence        []Evidence       `json:"evidence"`
	OpenQuestions   []string         `json:"open_questions"`
	SuggestedQueue  string           `json:"suggested_queue"`
	SuggestedAgents []SuggestedAgent `json:"suggested_agents"`
	SessionID       string           `json:"session_id"`
	TraceID         string           `json:"trace_id"`
	Resolution      *Resolution      `json:"resolution,omitempty"` // set when the claiming agent closes it
}

// Resolution is how the agent who claimed a handoff closed it. Stored inside the handoff payload.
type Resolution struct {
	Outcome  string    `json:"outcome"` // accepted | rejected
	Note     string    `json:"note"`
	ClosedBy string    `json:"closed_by"`
	ClosedAt time.Time `json:"closed_at"`
}

// CloseRequest is the body of POST /api/handoffs/{id}/close; Outcome is "accepted" or "rejected".
type CloseRequest struct {
	Outcome string `json:"outcome"`
	Note    string `json:"note"`
}

// MyDispute is one row of the customer's "Mis disputas" list: a case opened by the assistant or a handoff to a
// specialist. Transaction fields are empty for handoffs without an identified transaction.
type MyDispute struct {
	Kind        string      `json:"kind"` // case | handoff
	ID          string      `json:"id"`
	DisputeType string      `json:"dispute_type"`
	Status      string      `json:"status"`
	CreatedAt   time.Time   `json:"created_at"`
	Merchant    string      `json:"merchant,omitempty"`
	Amount      *float64    `json:"amount,omitempty"`
	Currency    string      `json:"currency,omitempty"`
	TxnDate     *time.Time  `json:"transaction_date,omitempty"`
	CardLast4   string      `json:"card_last4,omitempty"`
	Resolution  *Resolution `json:"resolution,omitempty"`
}

// HandoffSummary is one row of the agent queue (GET /api/handoffs).
type HandoffSummary struct {
	HandoffID   string     `json:"handoff_id"`
	CreatedAt   time.Time  `json:"created_at"`
	Status      string     `json:"status"`
	Language    string     `json:"language"`
	Reason      string     `json:"reason"`
	Priority    string     `json:"priority"`
	Queue       string     `json:"suggested_queue"`
	DisputeType string     `json:"dispute_type"`
	ClaimedBy   *string    `json:"claimed_by,omitempty"`
	ClaimedAt   *time.Time `json:"claimed_at,omitempty"`
}

// AuditEvent is one step of a session's audit trail (GET /api/sessions/{id}/audit).
type AuditEvent struct {
	TS        time.Time `json:"ts"`
	Step      string    `json:"step"`
	Tool      *string   `json:"tool"`
	Summary   string    `json:"summary"`
	Result    *string   `json:"result"`
	RuleID    *string   `json:"rule_id"`
	TraceID   *string   `json:"trace_id"`
	LatencyMS int       `json:"latency_ms"`
}

// OutcomeCount counts completed turns per outcome, language and mode (system or baseline).
type OutcomeCount struct {
	Outcome string `json:"outcome"`
	Lang    string `json:"lang"`
	Mode    string `json:"mode"`
	Count   int    `json:"count"`
}

// Summary is the response to GET /api/admin/summary: turn counts and latency percentiles from the audit trail.
type Summary struct {
	Turns        int            `json:"turns"`
	P50LatencyMS float64        `json:"p50_latency_ms"`
	P95LatencyMS float64        `json:"p95_latency_ms"`
	ByOutcome    []OutcomeCount `json:"by_outcome"`
	OpenHandoffs int            `json:"open_handoffs"`
}

// Analytics is the supervisor's "Resumen" for one time range. Everything is aggregated from the audit trail and
// the handoff queue (the only tables staff can read): counts and latencies, never customer data.
type Analytics struct {
	Range       string        `json:"range"`  // 24h | 7d | 30d | all
	From        *time.Time    `json:"from"`   // start of the range; null for "all"
	Bucket      string        `json:"bucket"` // hour | day: granularity of Series
	KPIs        AnalyticsKPIs `json:"kpis"`
	Series      []SeriesPoint `json:"series"`       // answers per bucket, by mode and outcome
	ByMode      []ModeOutcome `json:"by_mode"`      // assistant vs baseline: how answers ended
	ByLang      []LabelCount  `json:"by_lang"`      // conversations per language (assistant)
	TopRules    []LabelCount  `json:"top_rules"`    // policy rule that decided each answer (assistant)
	Handoffs    []ReasonCount `json:"handoffs"`     // cases handed to a person, by reason and priority
	Funnel      []FunnelStep  `json:"funnel"`       // conversations reaching each step (assistant)
	StepLatency []StepLatency `json:"step_latency"` // where the time goes inside a turn
}

// AnalyticsKPIs counts the assistant (mode=system) only; the baseline is in ByMode and Series.
type AnalyticsKPIs struct {
	Conversations      int     `json:"conversations"`
	Turns              int     `json:"turns"`
	CasesOpened        int     `json:"cases_opened"`
	CardsBlocked       int     `json:"cards_blocked"`
	Explained          int     `json:"explained"` // charges explained instead of disputed (EXPLAIN-* rules)
	Escalated          int     `json:"escalated"` // answers that handed the case to a person
	InjectionsBlocked  int     `json:"injections_blocked"`
	TechFailures       int     `json:"tech_failures"`
	P50LatencyMS       float64 `json:"p50_latency_ms"`
	P95LatencyMS       float64 `json:"p95_latency_ms"`
	HandoffsOpen       int     `json:"handoffs_open"` // waiting now, whatever the range
	HandoffsClaimed    int     `json:"handoffs_claimed"`
	HandoffsClosed     int     `json:"handoffs_closed"`
	MedianClaimSeconds float64 `json:"median_claim_seconds"`
	Accepted           int     `json:"accepted"`
	Rejected           int     `json:"rejected"`
	EmailsSent         int     `json:"emails_sent"`
	EmailsFailed       int     `json:"emails_failed"`
}

// SeriesPoint is the number of answers with a given mode and outcome in one time bucket.
type SeriesPoint struct {
	Bucket  time.Time `json:"bucket"`
	Mode    string    `json:"mode"`
	Outcome string    `json:"outcome"`
	Count   int       `json:"count"`
}

// ModeOutcome counts answers per mode (system or baseline) and outcome.
type ModeOutcome struct {
	Mode    string `json:"mode"`
	Outcome string `json:"outcome"`
	Count   int    `json:"count"`
}

// LabelCount is a generic label/count pair (language, policy rule id).
type LabelCount struct {
	Label string `json:"label"`
	Count int    `json:"count"`
}

// ReasonCount counts handoffs per escalation reason and priority.
type ReasonCount struct {
	Reason   string `json:"reason"`
	Priority string `json:"priority"`
	Count    int    `json:"count"`
}

// FunnelStep is how many conversations reached one step of the dispute flow.
type FunnelStep struct {
	Step     string `json:"step"` // understood | found | proposed | confirmed | verified
	Sessions int    `json:"sessions"`
}

// StepLatency is the average and p95 duration of one audited pipeline step.
type StepLatency struct {
	Step  string  `json:"step"`
	AvgMS float64 `json:"avg_ms"`
	P95MS float64 `json:"p95_ms"`
	Count int     `json:"count"`
}

// AdminConfig is the response to GET /api/admin/config: the active policy, model provider and versions.
type AdminConfig struct {
	PolicyVersion   string `json:"policy_version"`
	PolicyOrigin    string `json:"policy_origin"`
	Policy          any    `json:"policy"`
	LLMProvider     string `json:"llm_provider"`
	PromptVersion   string `json:"prompt_version"`
	ClassifierModel string `json:"classifier_model"`
	DemoToday       string `json:"demo_today"`
}

// Card is one of the customer's cards as shown on the home screen (last four digits only).
type Card struct {
	Last4  string `json:"last4"`
	Type   string `json:"type"`
	Status string `json:"status"`
}

// Overview is the customer's own home screen data: first name, cards and recent card movements.
type Overview struct {
	FirstName string      `json:"first_name"`
	Cards     []Card      `json:"cards"`
	Recent    []Candidate `json:"recent"`
	Today     string      `json:"today"`
}

// CustomerIdentity is revealed only to the agent who claimed a handoff, and every reveal is audited.
type CustomerIdentity struct {
	CustomerRef string `json:"customer_ref"`
	FirstName   string `json:"first_name"`
	LastName    string `json:"last_name"`
}
