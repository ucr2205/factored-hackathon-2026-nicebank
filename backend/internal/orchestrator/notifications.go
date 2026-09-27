package orchestrator

import (
	"encoding/json"
	"strings"
)

// queueNotification writes an email to the outbox inside the turn's transaction, so it exists only if the
// action it announces committed. The notifier worker delivers it. Baseline runs (evaluation) send nothing.
func (t *turn) queueNotification(kind string, facts map[string]string) {
	if t.mode == "baseline" {
		return
	}
	payload := map[string]string{}
	for k, v := range facts {
		payload[k] = v
	}
	raw, _ := json.Marshal(payload)
	if _, err := t.tx.Exec(t.ctx, `INSERT INTO notifications (session_id, kind, lang, payload) VALUES ($1, $2, $3, $4)`,
		t.s.ID, kind, t.lang, raw); err != nil {
		t.audit("notify", "queue_email", "could not queue "+kind+": "+err.Error(), "failed", "", 0)
		return
	}
	t.notified = append(t.notified, kind)
	t.audit("notify", "queue_email", "email "+kind+" queued", "queued", "", 0)
}

func (t *turn) hasNotified(kind string) bool {
	for _, k := range t.notified {
		if k == kind {
			return true
		}
	}
	return false
}

// shortRef is what the customer sees for a handoff: the first 8 characters of its id.
func shortRef(id string) string {
	if len(id) > 8 {
		id = id[:8]
	}
	return strings.ToUpper(id)
}
