# ADR 0001 — One supervised conversational agent, deterministic orchestration

- Status: Accepted
- Date: 2026-09-26

## Context

The challenge asks for an AI-first customer-service system that knows when *not* to act. Judges assess
controlled automation: permissions and policy enforced outside model-generated prose, only verified actions
reported, and audit evidence that comes from execution records rather than model reasoning. The problem
statement notes that multi-agent designs are not required and earn no automatic bonus.

The team has experience with multi-agent frameworks and considered using several autonomous agents at runtime.

## Decision

At runtime the product uses **a single conversational LLM agent supervised by a deterministic orchestrator in Go**:

- The LLM *proposes*: it extracts facts from free text, drafts clarifying questions, writes customer replies
  from verified facts and retrieved policy, and writes the natural-language summary inside a handoff.
- The Go orchestrator *decides and acts*: a state machine (Understand → Decide → Act → Verify → Respond/Escalate)
  validates every proposal against `policies/disputes.yaml` and a per-state tool allowlist, executes simulated
  bank tools, verifies each write by reading it back, and records every step in `audit_events`.
- "Specialist" behaviors (extraction, classification, drafting, handoff summary) are bounded steps with their
  own versioned prompts, not independent agents.
- Multi-agent tooling may be used by the team for **internal work** (generating test-case paraphrases, running
  nightly evaluations, reviewing code). Its outputs are labeled `origin: team_generated` and are never part of
  the evaluated runtime path.

## Consequences

- Deterministic, reproducible behavior for evaluation; lower latency and cost per case.
- Every action is explainable by a policy rule id and an execution record.
- Less flexibility for open-ended requests; those are handled by abstention or human handoff, which is the
  intended behavior for a banking workflow.
