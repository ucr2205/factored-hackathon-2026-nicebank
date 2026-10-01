// Package llm defines the language-model boundary. The model only extracts facts from free text and drafts
// customer-facing wording from verified facts; it never decides or executes actions.
package llm

import (
	"context"
	"time"
)

// Extraction holds facts the model pulled out of a customer message. All fields are optional.
type Extraction struct {
	Amount       *float64   `json:"amount,omitempty"`
	DateFrom     *time.Time `json:"date_from,omitempty"`
	DateTo       *time.Time `json:"date_to,omitempty"`
	MerchantHint string     `json:"merchant_hint,omitempty"`
	// Refuse is the model's opinion that the message must be refused whatever its dispute type: "third_party_data",
	// "instruction_override" or "bypass_process"; empty for normal messages. It is never merged into the
	// conversation state: it only concerns the message it came with.
	Refuse string `json:"-"`
}

// RefuseReasons are the values Extraction.Refuse may take.
var RefuseReasons = map[string]bool{"third_party_data": true, "instruction_override": true, "bypass_process": true}

// Merge keeps previously extracted facts unless the new message provides them.
func (e Extraction) Merge(next Extraction) Extraction {
	if next.Amount != nil {
		e.Amount = next.Amount
	}
	if next.DateFrom != nil {
		e.DateFrom, e.DateTo = next.DateFrom, next.DateTo
	}
	if next.MerchantHint != "" {
		e.MerchantHint = next.MerchantHint
	}
	return e
}

type Usage struct {
	InputTokens  int
	OutputTokens int
	CostUSD      float64
}

// ComposeInput is everything the model may use to word a reply. Facts are already verified by the backend.
type ComposeInput struct {
	Intent string            // e.g. "confirm_open_case", "case_opened", "clarify_multi"
	Lang   string            // "es" | "pt"
	Facts  map[string]string // verified values only (amounts, dates, references)
}

type Provider interface {
	Name() string
	Version() string
	Extract(ctx context.Context, maskedText, lang string, today time.Time) (Extraction, Usage, error)
	// PickCandidate returns the index chosen by the customer's reply ("la segunda", "2"), or -1.
	PickCandidate(ctx context.Context, maskedText string, merchants []string) (int, Usage, error)
	Compose(ctx context.Context, in ComposeInput) (string, Usage, error)
}
