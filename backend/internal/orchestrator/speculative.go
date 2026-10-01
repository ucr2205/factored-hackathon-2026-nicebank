package orchestrator

import (
	"context"

	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/telemetry"
)

type extraction struct {
	ex llm.Extraction
	u  llm.Usage
}

// startExtraction runs the LLM fact extraction concurrently with classification: both only read the masked
// text, so a turn takes max(classify, extract) instead of their sum. The goroutine touches neither the
// database transaction (pgx.Tx is not safe for concurrent use) nor the turn state; it only reports its result.
//
// Exactly one of the returned functions must be called: wait when the message is a dispute and the facts are
// needed, discard otherwise (out of scope, unclear type, card lost or stolen, classifier failure). discard
// cancels the model call; if the call already finished, its real cost is still counted.
func (t *turn) startExtraction(masked string) (wait func() extraction, discard func()) {
	ctx, cancel := context.WithCancel(t.ctx)
	done := make(chan extraction, 1) // buffered: the goroutine never blocks, even when nobody reads it
	model, lang, country, today := t.o.LLM, t.lang, t.country, t.o.Today
	go func() {
		ex, u, _ := model.Extract(ctx, masked, lang, country, today)
		done <- extraction{ex, u}
	}()

	wait = func() extraction {
		defer cancel()
		r := <-done
		telemetry.SpeculativeExtractions.WithLabelValues("used").Inc()
		return r
	}
	discard = func() {
		cancel()
		select {
		case r := <-done:
			t.addUsage(r.u)
		default:
		}
		telemetry.SpeculativeExtractions.WithLabelValues("discarded").Inc()
	}
	return wait, discard
}
