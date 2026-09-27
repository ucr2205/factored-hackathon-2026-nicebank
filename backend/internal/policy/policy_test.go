package policy

import "testing"

func loadRepoPolicy(t *testing.T) *Policy {
	t.Helper()
	p, err := Load("../../../policies/disputes.yaml")
	if err != nil {
		t.Fatalf("load policy: %v", err)
	}
	return p
}

func TestEvaluate(t *testing.T) {
	p := loadRepoPolicy(t)
	cases := []struct {
		name   string
		facts  Facts
		kind   Kind
		ruleID string
	}{
		{"small unrecognized charge is automatic", Facts{"unrecognized_charge", 5, "Approved", 120}, Auto, "DISP-AUTO-01"},
		{"large unrecognized charge escalates with card block", Facts{"unrecognized_charge", 2, "Approved", 1450}, Escalate, "DISP-ESC-01"},
		{"old charge is not automatic", Facts{"unrecognized_charge", 200, "Approved", 50}, Ineligible, "DISP-ELIG-01"},
		{"reversed charge is not automatic", Facts{"duplicate_charge", 3, "Reversed", 50}, Ineligible, "DISP-ELIG-01"},
		{"duplicate under limit is automatic", Facts{"duplicate_charge", 2, "Approved", 89.9}, Auto, "DISP-AUTO-02"},
		{"stolen card always escalates", Facts{"card_lost_stolen", 0, "", 0}, Escalate, "DISP-ESC-02"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			d, err := p.Evaluate(c.facts)
			if err != nil {
				t.Fatal(err)
			}
			if d.Kind != c.kind || d.RuleID != c.ruleID {
				t.Fatalf("got %s/%s, want %s/%s", d.Kind, d.RuleID, c.kind, c.ruleID)
			}
		})
	}
	if d, _ := p.Evaluate(Facts{"unrecognized_charge", 2, "Approved", 1450}); d.SuggestAction != "block_card" {
		t.Fatalf("high-amount unrecognized charge should suggest block_card, got %q", d.SuggestAction)
	}
}

func TestUnknownTypeFails(t *testing.T) {
	if _, err := loadRepoPolicy(t).Evaluate(Facts{DisputeType: "nope"}); err == nil {
		t.Fatal("expected error for unknown dispute type")
	}
}
