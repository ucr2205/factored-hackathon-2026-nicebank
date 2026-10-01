// Package contract holds the JSON shapes of the public API (docs/api/contracts.md).
// Keep in sync with frontend/src/api/types.ts.
package contract

import "time"

type ChatRequest struct {
	SessionID           *string `json:"session_id"`
	Message             string  `json:"message"`
	Lang                string  `json:"lang"`
	SelectTransactionID *string `json:"select_transaction_id"`
}

type ConfirmRequest struct {
	SessionID string `json:"session_id"`
	ActionID  string `json:"action_id"`
	Confirm   bool   `json:"confirm"`
}

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

type PendingAction struct {
	ID             string `json:"id"`
	Type           string `json:"type"`
	Summary        string `json:"summary"`
	RequiresStepUp bool   `json:"requires_step_up"`
}

type VerifiedAction struct {
	Type       string    `json:"type"`
	Reference  string    `json:"reference"`
	VerifiedAt time.Time `json:"verified_at"`
}

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

type Message struct {
	Role string    `json:"role"`
	Text string    `json:"text"`
	At   time.Time `json:"at"`
}

type SessionView struct {
	SessionID     string         `json:"session_id"`
	Lang          string         `json:"lang"`
	Messages      []Message      `json:"messages"`
	PendingAction *PendingAction `json:"pending_action,omitempty"`
}

type Fact struct {
	Fact   string `json:"fact"`
	Source string `json:"source"`
}

type ActionTaken struct {
	Action    string    `json:"action"`
	Status    string    `json:"status"`
	Reference string    `json:"reference"`
	At        time.Time `json:"at"`
}

type Evidence struct {
	Type string `json:"type"`
	ID   string `json:"id"`
}

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

type OutcomeCount struct {
	Outcome string `json:"outcome"`
	Lang    string `json:"lang"`
	Mode    string `json:"mode"`
	Count   int    `json:"count"`
}

type Summary struct {
	Turns        int            `json:"turns"`
	P50LatencyMS float64        `json:"p50_latency_ms"`
	P95LatencyMS float64        `json:"p95_latency_ms"`
	ByOutcome    []OutcomeCount `json:"by_outcome"`
	OpenHandoffs int            `json:"open_handoffs"`
}

type AdminConfig struct {
	PolicyVersion   string `json:"policy_version"`
	PolicyOrigin    string `json:"policy_origin"`
	Policy          any    `json:"policy"`
	LLMProvider     string `json:"llm_provider"`
	PromptVersion   string `json:"prompt_version"`
	ClassifierModel string `json:"classifier_model"`
	DemoToday       string `json:"demo_today"`
}

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
