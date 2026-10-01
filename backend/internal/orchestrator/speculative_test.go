package orchestrator

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
)

// slowModel waits before answering, like a remote LLM, and records whether its call was cancelled.
type slowModel struct {
	llm.Fake
	delay     time.Duration
	cancelled atomic.Bool
}

func (m *slowModel) Extract(ctx context.Context, text, lang, _ string, today time.Time) (llm.Extraction, llm.Usage, error) {
	select {
	case <-time.After(m.delay):
		amount := 12.5
		return llm.Extraction{Amount: &amount}, llm.Usage{InputTokens: 100, CostUSD: 0.001}, nil
	case <-ctx.Done():
		m.cancelled.Store(true)
		return llm.Extraction{}, llm.Usage{}, ctx.Err()
	}
}

func newTestTurn(m llm.Provider) *turn {
	return &turn{o: &Orchestrator{LLM: m, Today: time.Date(2026, 6, 17, 0, 0, 0, 0, time.UTC)}, ctx: context.Background(), lang: "es"}
}

// The extraction overlaps the (simulated) classification instead of running after it.
func TestExtractionRunsWhileClassifying(t *testing.T) {
	m := &slowModel{delay: 150 * time.Millisecond}
	tr := newTestTurn(m)
	start := time.Now()
	wait, _ := tr.startExtraction("cargo de 12,50")
	time.Sleep(120 * time.Millisecond) // the classifier's share of the turn
	r := wait()
	if took := time.Since(start); took > 250*time.Millisecond {
		t.Fatalf("took %v: extraction did not overlap classification (sequential would be ~270ms)", took)
	}
	if r.ex.Amount == nil || *r.ex.Amount != 12.5 || r.u.InputTokens != 100 {
		t.Fatalf("unexpected result %+v", r)
	}
}

// When the message is not a dispute the model call is cancelled and nothing is billed to the turn.
func TestDiscardCancelsTheModelCall(t *testing.T) {
	m := &slowModel{delay: time.Second}
	tr := newTestTurn(m)
	_, discard := tr.startExtraction("quero um empréstimo")
	discard()
	deadline := time.Now().Add(500 * time.Millisecond)
	for !m.cancelled.Load() && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if !m.cancelled.Load() {
		t.Fatal("the model call was not cancelled")
	}
	if tr.usage.CostUSD != 0 {
		t.Fatalf("a cancelled call must not add cost, got %v", tr.usage.CostUSD)
	}
}

// A call that already finished before being discarded still counts: its tokens were paid for.
func TestDiscardCountsAFinishedCall(t *testing.T) {
	m := &slowModel{delay: time.Millisecond}
	tr := newTestTurn(m)
	_, discard := tr.startExtraction("quero um empréstimo")
	time.Sleep(50 * time.Millisecond)
	discard()
	if tr.usage.CostUSD != 0.001 {
		t.Fatalf("finished call cost not counted: %v", tr.usage.CostUSD)
	}
}
