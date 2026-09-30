// Package policy loads policies/disputes.yaml and makes the deterministic decisions for a dispute.
// The language model never decides eligibility or actions; this package does, and returns the rule id
// that justifies each decision so it can be audited.
package policy

import (
	"fmt"
	"os"
	"slices"

	"gopkg.in/yaml.v3"
)

type Rule struct {
	RuleID      string `yaml:"rule_id" json:"rule_id"`
	When        string `yaml:"when" json:"when"`
	Outcome     string `yaml:"outcome" json:"outcome"`
	Description string `yaml:"description" json:"description"`
}

type Escalation struct {
	RuleID        string `yaml:"rule_id" json:"rule_id"`
	Condition     string `yaml:"condition" json:"condition"`
	Reason        string `yaml:"reason" json:"reason"`
	SuggestAction string `yaml:"suggest_action" json:"suggest_action,omitempty"`
	Queue         string `yaml:"queue" json:"queue"`
}

// StatusRule explains a charge that is not a final debit (reversed, declined, pending) before any dispute.
type StatusRule struct {
	RuleID        string   `yaml:"rule_id" json:"rule_id"`
	Status        string   `yaml:"status" json:"status"`
	Types         []string `yaml:"types" json:"types,omitempty"` // empty: every dispute type
	SuggestAction string   `yaml:"suggest_action" json:"suggest_action,omitempty"`
	Reason        string   `yaml:"reason" json:"reason,omitempty"`
	Queue         string   `yaml:"queue" json:"queue,omitempty"`
	Description   string   `yaml:"description" json:"description"`
}

type DisputeType struct {
	ID          string            `yaml:"id" json:"id"`
	DisplayName map[string]string `yaml:"display_name" json:"display_name"`
	EligibleIf  struct {
		MaxAgeDays        int      `yaml:"max_age_days" json:"max_age_days"`
		TransactionStatus []string `yaml:"transaction_status" json:"transaction_status"`
	} `yaml:"eligible_if" json:"eligible_if"`
	AutoAction       string       `yaml:"auto_action" json:"auto_action"`
	MaxAutoAmountUSD float64      `yaml:"max_auto_amount_usd" json:"max_auto_amount_usd"`
	EscalateIf       []Escalation `yaml:"escalate_if" json:"escalate_if"`
	AlwaysEscalate   *Escalation  `yaml:"always_escalate" json:"always_escalate,omitempty"`
	Rules            struct {
		Auto       string `yaml:"auto" json:"auto"`
		Ineligible string `yaml:"ineligible" json:"ineligible"`
	} `yaml:"rules" json:"rules"`
}

type Policy struct {
	Version  string `yaml:"version" json:"version"`
	Origin   string `yaml:"origin" json:"origin"`
	Currency string `yaml:"currency" json:"currency"`
	Globals  struct {
		Never              []string     `yaml:"never" json:"never"`
		StepUpActions      []string     `yaml:"step_up_actions" json:"step_up_actions"`
		ConfirmActions     []string     `yaml:"confirm_actions" json:"confirm_actions"`
		SessionIdleMinutes int          `yaml:"session_idle_minutes" json:"session_idle_minutes"`
		MaxCandidatesShown int          `yaml:"max_candidates_shown" json:"max_candidates_shown"`
		MaxClarifications  int          `yaml:"max_clarifications" json:"max_clarifications"`
		Rules              []Rule       `yaml:"rules" json:"rules"`
		ExplainStatus      []StatusRule `yaml:"explain_status" json:"explain_status"`
	} `yaml:"globals" json:"globals"`
	DisputeTypes []DisputeType `yaml:"dispute_types" json:"dispute_types"`
}

// Load reads and validates the policy file. An invalid policy must stop the service from starting.
func Load(path string) (*Policy, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read policy: %w", err)
	}
	var p Policy
	if err := yaml.Unmarshal(raw, &p); err != nil {
		return nil, fmt.Errorf("parse policy: %w", err)
	}
	return &p, p.validate()
}

func (p *Policy) validate() error {
	if p.Version == "" || p.Currency != "USD" {
		return fmt.Errorf("policy: version required and currency must be USD")
	}
	if p.Globals.MaxClarifications < 1 || p.Globals.MaxCandidatesShown < 1 {
		return fmt.Errorf("policy: max_clarifications and max_candidates_shown must be >= 1")
	}
	seen := map[string]bool{}
	for _, d := range p.DisputeTypes {
		if d.ID == "" || seen[d.ID] {
			return fmt.Errorf("policy: dispute type id missing or duplicated: %q", d.ID)
		}
		seen[d.ID] = true
		if d.AutoAction != "open_dispute_case" && d.AutoAction != "block_card" {
			return fmt.Errorf("policy: %s has unsupported auto_action %q", d.ID, d.AutoAction)
		}
		if d.DisplayName["es"] == "" || d.DisplayName["pt"] == "" {
			return fmt.Errorf("policy: %s needs es and pt display names", d.ID)
		}
		if d.AlwaysEscalate == nil && (d.EligibleIf.MaxAgeDays <= 0 || d.MaxAutoAmountUSD <= 0) {
			return fmt.Errorf("policy: %s needs max_age_days and max_auto_amount_usd", d.ID)
		}
	}
	for _, r := range p.Globals.ExplainStatus {
		if r.RuleID == "" || !slices.Contains([]string{"Reversed", "Declined", "Pending"}, r.Status) {
			return fmt.Errorf("policy: explain_status rule %q needs a rule_id and a Reversed, Declined or Pending status", r.RuleID)
		}
		for _, id := range r.Types {
			if !seen[id] {
				return fmt.Errorf("policy: explain_status rule %s names unknown dispute type %q", r.RuleID, id)
			}
		}
		if r.SuggestAction != "" && (r.SuggestAction != "block_card" || r.Queue == "" || r.Reason == "") {
			return fmt.Errorf("policy: explain_status rule %s: suggest_action must be block_card, with queue and reason", r.RuleID)
		}
	}
	return nil
}

func (p *Policy) Type(id string) (DisputeType, bool) {
	for _, d := range p.DisputeTypes {
		if d.ID == id {
			return d, true
		}
	}
	return DisputeType{}, false
}

func (p *Policy) RequiresStepUp(action string) bool {
	return slices.Contains(p.Globals.StepUpActions, action)
}

// Outcome of evaluating one identified transaction against the policy.
type Kind string

const (
	Auto       Kind = "auto"       // open the case automatically after customer confirmation
	Escalate   Kind = "escalate"   // hand off to a human (optionally after a protective action)
	Ineligible Kind = "ineligible" // outside the automatic window; a human reviews it
	Explain    Kind = "explain"    // not a final debit: explain it with the record (optionally proposing a card block)
)

type Decision struct {
	Kind          Kind
	RuleID        string
	Reason        string
	SuggestAction string
	Queue         string
}

type Facts struct {
	DisputeType string
	AgeDays     int
	Status      string
	AmountUSD   float64
}

func (p *Policy) Evaluate(f Facts) (Decision, error) {
	d, ok := p.Type(f.DisputeType)
	if !ok {
		return Decision{}, fmt.Errorf("unknown dispute type %q", f.DisputeType)
	}
	if e := d.AlwaysEscalate; e != nil {
		return Decision{Kind: Escalate, RuleID: e.RuleID, Reason: e.Reason, SuggestAction: d.AutoAction, Queue: e.Queue}, nil
	}
	// A reversed, declined or pending charge is explained first, whatever its age or amount.
	for _, r := range p.Globals.ExplainStatus {
		if r.Status == f.Status && (len(r.Types) == 0 || slices.Contains(r.Types, f.DisputeType)) {
			return Decision{Kind: Explain, RuleID: r.RuleID, Reason: r.Reason, SuggestAction: r.SuggestAction, Queue: r.Queue}, nil
		}
	}
	if f.AgeDays > d.EligibleIf.MaxAgeDays || !slices.Contains(d.EligibleIf.TransactionStatus, f.Status) {
		return Decision{Kind: Ineligible, RuleID: d.Rules.Ineligible, Reason: "outside_automatic_window", Queue: "disputes"}, nil
	}
	for _, e := range d.EscalateIf {
		if e.Condition == "amount_over_max" && f.AmountUSD > d.MaxAutoAmountUSD {
			return Decision{Kind: Escalate, RuleID: e.RuleID, Reason: e.Reason, SuggestAction: e.SuggestAction, Queue: e.Queue}, nil
		}
	}
	return Decision{Kind: Auto, RuleID: d.Rules.Auto, Reason: "eligible", Queue: "disputes"}, nil
}
