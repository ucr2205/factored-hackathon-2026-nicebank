package orchestrator

import (
	"strings"

	"github.com/factored-hackathon-2026/disputes/backend/internal/guard"
	"github.com/factored-hackathon-2026/disputes/backend/internal/textnorm"
)

// baseline approximates today's process for the evaluation harness: a keyword router with no model and no
// tools. In-scope disputes always go to a human; out-of-scope requests are redirected; anything else is asked again.
func (t *turn) baseline(msg string) error {
	n := textnorm.Normalize(msg)
	st := &t.s.State
	switch {
	case containsAny(n, "prestamo", "credito", "emprestimo", "inversion", "investimento"):
		return t.reply("abstain", "abstain_scope", nil, "SCOPE-01")
	case containsAny(n, "robaron", "roubaram", "perdi"):
		st.DisputeType = "card_lost_stolen"
	case containsAny(n, "dos veces", "duas vezes", "duplicad", "doble"):
		st.DisputeType = "duplicate_charge"
	case containsAny(n, "no reconozco", "nao reconheco", "no hice", "nao fiz", "fraude", "cobro", "cargo", "cobranca"):
		st.DisputeType = "unrecognized_charge"
	default:
		return t.clarify("clarify_type", "CLARIFY-TYPE")
	}
	st.FirstMessage = guard.Mask(msg, t.names...)
	return t.escalate("baseline_human_review", "BASELINE-01", "handoff_created", nil, "disputes", nil)
}

func containsAny(s string, subs ...string) bool {
	for _, sub := range subs {
		if strings.Contains(s, sub) {
			return true
		}
	}
	return false
}
