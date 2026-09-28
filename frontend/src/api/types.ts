// API shapes — keep in sync with docs/api/contracts.md and backend/internal/contract/contract.go.

export type Outcome = "resolve" | "clarify" | "abstain" | "escalate" | "confirm";

export type Candidate = {
  transaction_id: string;
  date: string;
  amount: number;
  currency: string;
  merchant: string;
  city: string;
  country: string;
  card_last4: string;
};

export type PendingAction = {
  id: string;
  type: "open_dispute_case" | "block_card";
  summary: string;
  requires_step_up: boolean;
};

export type VerifiedAction = { type: string; reference: string; verified_at: string };

export type ChatTurn = {
  session_id: string;
  reply: string;
  outcome: Outcome;
  candidates?: Candidate[];
  pending_action?: PendingAction;
  actions_verified: VerifiedAction[];
  case_id: string | null;
  handoff_id: string | null;
  rule_ids: string[];
  trace_id: string;
  latency_ms: number;
  cost_usd: number;
  mode: "system" | "baseline";
};

export type SessionView = {
  session_id: string;
  lang: "es" | "pt";
  messages: { role: "customer" | "assistant"; text: string; at: string }[];
  pending_action?: PendingAction;
};

export type HandoffSummary = {
  handoff_id: string;
  created_at: string;
  status: "open" | "claimed" | "closed";
  language: "es" | "pt";
  reason: string;
  priority: "high" | "medium" | "low";
  suggested_queue: string;
  dispute_type: string;
  claimed_by?: string;
  claimed_at?: string;
};

export type Handoff = HandoffSummary & {
  customer_request: string;
  verified_facts: { fact: string; source: string }[];
  actions_taken: { action: string; status: string; reference: string; at: string }[];
  evidence: { type: string; id: string }[];
  open_questions: string[];
  suggested_agents: { agent_id: string; name: string; languages: string; specialty: string }[] | null;
  session_id: string;
  trace_id: string;
};

export type AuditEvent = {
  ts: string;
  step: string;
  tool: string | null;
  summary: string;
  result: string | null;
  rule_id: string | null;
  trace_id: string | null;
  latency_ms: number;
};

export type Summary = {
  turns: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  by_outcome: { outcome: string; lang: string; mode: string; count: number }[];
  open_handoffs: number;
};

export type PolicyRule = { rule_id: string; when: string; outcome: string; description: string };

export type PolicyEscalation = { rule_id: string; condition?: string; reason: string; suggest_action?: string; queue: string };

export type PolicyDisputeType = {
  id: string;
  display_name: Record<string, string>;
  max_auto_amount_usd: number;
  auto_action: string;
  eligible_if: { max_age_days: number; transaction_status?: string[] | null };
  escalate_if: PolicyEscalation[] | null;
  always_escalate?: PolicyEscalation;
  rules: { auto: string; ineligible: string };
};

export type AdminConfig = {
  policy_version: string;
  policy_origin: string;
  policy: {
    globals: {
      rules: PolicyRule[];
      never: string[];
      step_up_actions: string[];
      confirm_actions: string[];
      session_idle_minutes: number;
      max_candidates_shown: number;
      max_clarifications: number;
    };
    dispute_types: PolicyDisputeType[];
  };
  llm_provider: string;
  prompt_version: string;
  classifier_model: string;
  demo_today: string;
};

export type Overview = {
  first_name: string;
  cards: { last4: string; type: string; status: string }[];
  recent: Candidate[];
  today: string;
};

/** Revealed only to the agent who claimed the handoff; every reveal is audited. */
export type CustomerIdentity = {
  customer_ref: string;
  first_name: string;
  last_name: string;
};
