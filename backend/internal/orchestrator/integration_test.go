//go:build integration

// Integration tests against the running Postgres of the docker compose stack (seeded with make seed).
//
//	TEST_DATABASE_URL=postgres://app_user:<APP_DB_PASSWORD>@localhost:5433/bank go test -tags integration ./internal/orchestrator/
//
// They connect as the application role, so row-level security applies exactly as in production. The ml-service
// is replaced by a local stub (or by a closed port), and the LLM by the fake provider. The ml-service-down test
// queues a handoff email: run the backend on Mailpit, not on a real SMTP server.
package orchestrator

import (
	"context"
	"encoding/csv"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/factored-hackathon-2026/disputes/backend/internal/auth"
	"github.com/factored-hackathon-2026/disputes/backend/internal/contract"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/mlclient"
	"github.com/factored-hackathon-2026/disputes/backend/internal/policy"
	"github.com/factored-hackathon-2026/disputes/backend/internal/store"
)

var demoToday = time.Date(2026, 6, 17, 0, 0, 0, 0, time.UTC)

// demoRefs returns the opaque customer_ref of the first two demo customers (etl/seeds/demo_customers.csv).
func demoRefs(t *testing.T) (string, string) {
	t.Helper()
	f, err := os.Open(filepath.Join("..", "..", "..", "etl", "seeds", "demo_customers.csv"))
	if err != nil {
		t.Fatalf("demo customers: %v", err)
	}
	defer f.Close()
	rows, err := csv.NewReader(f).ReadAll()
	if err != nil || len(rows) < 3 {
		t.Fatalf("demo customers csv: %v", err)
	}
	return rows[1][2], rows[2][2]
}

func newOrchestrator(t *testing.T, mlURL string, idle time.Duration) *Orchestrator {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	s, err := store.Open(context.Background(), url)
	if err != nil {
		t.Fatalf("store: %v", err)
	}
	t.Cleanup(s.Close)
	p, err := policy.Load(filepath.Join("..", "..", "..", "policies", "disputes.yaml"))
	if err != nil {
		t.Fatalf("policy: %v", err)
	}
	return New(s, p, mlclient.New(mlURL), llm.Fake{}, demoToday, idle)
}

// mlStub answers /classify with a fixed C2 response.
func mlStub(t *testing.T, body string) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
	t.Cleanup(srv.Close)
	return srv.URL
}

func customer(ref string) auth.Principal {
	return auth.Principal{Subject: "it-" + ref, Username: "integration-test", CustomerRef: ref, Roles: []string{"customer"}, ACR: 1}
}

func TestRLSIsolatesCustomers(t *testing.T) {
	o := newOrchestrator(t, mlStub(t, `{"label":"out_of_scope","confidence":0.9,"abstain":false,"model_version":"stub"}`), 15*time.Minute)
	ref1, ref2 := demoRefs(t)
	ctx := context.Background()

	// Inside a customer transaction, no row of another customer is visible, in any table.
	err := o.Store.WithCustomer(ctx, ref1, func(tx pgx.Tx) error {
		var own, foreign int
		if err := tx.QueryRow(ctx, `SELECT count(*) FILTER (WHERE customer_id = current_setting('app.customer_id')),
			count(*) FILTER (WHERE customer_id <> current_setting('app.customer_id')) FROM transactions`).Scan(&own, &foreign); err != nil {
			return err
		}
		if own == 0 || foreign != 0 {
			t.Errorf("transactions visible: own=%d foreign=%d, want own>0 and foreign=0", own, foreign)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}

	// A session created by customer 1 does not exist for customer 2.
	out, err := o.HandleMessage(ctx, customer(ref1), contract.ChatRequest{Message: "quiero un préstamo", Lang: "es"}, "system")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := o.Session(ctx, customer(ref2), out.SessionID); !errors.Is(err, ErrNotFound) {
		t.Errorf("other customer's session: got %v, want ErrNotFound", err)
	}
	if _, err := o.HandleMessage(ctx, customer(ref2), contract.ChatRequest{SessionID: &out.SessionID, Message: "hola", Lang: "es"}, "system"); !errors.Is(err, ErrNotFound) {
		t.Errorf("writing to another customer's session: got %v, want ErrNotFound", err)
	}

	// An unknown customer_ref pins nothing and fails closed.
	if err := o.Store.WithCustomer(ctx, "cr_unknown", func(pgx.Tx) error { return nil }); !errors.Is(err, store.ErrNoCustomer) {
		t.Errorf("unknown ref: got %v, want ErrNoCustomer", err)
	}
}

func TestExpiredSessionIsRejected(t *testing.T) {
	o := newOrchestrator(t, mlStub(t, `{"label":"out_of_scope","confidence":0.9,"abstain":false,"model_version":"stub"}`), 50*time.Millisecond)
	ref1, _ := demoRefs(t)
	ctx := context.Background()
	out, err := o.HandleMessage(ctx, customer(ref1), contract.ChatRequest{Message: "quiero un préstamo", Lang: "es"}, "system")
	if err != nil {
		t.Fatal(err)
	}
	time.Sleep(200 * time.Millisecond) // longer than the idle timeout
	_, err = o.HandleMessage(ctx, customer(ref1), contract.ChatRequest{SessionID: &out.SessionID, Message: "hola", Lang: "es"}, "system")
	if !errors.Is(err, ErrSessionExpired) {
		t.Errorf("got %v, want ErrSessionExpired", err)
	}
}

func TestClassifierDownEscalatesToHuman(t *testing.T) {
	o := newOrchestrator(t, "http://127.0.0.1:1", 15*time.Minute) // nothing listens on port 1
	ref1, _ := demoRefs(t)
	out, err := o.HandleMessage(context.Background(), customer(ref1),
		contract.ChatRequest{Message: "No reconozco un cobro de 50 dólares de ayer", Lang: "es"}, "system")
	if err != nil {
		t.Fatal(err)
	}
	if out.Outcome != "escalate" || !slices.Contains(out.RuleIDs, "ESC-TECH-01") || out.HandoffID == nil {
		t.Errorf("got outcome=%s rules=%v handoff=%v, want escalate with ESC-TECH-01 and a handoff", out.Outcome, out.RuleIDs, out.HandoffID)
	}
}

func TestCloseClaimedHandoffAndShowItToTheCustomer(t *testing.T) {
	o := newOrchestrator(t, "http://127.0.0.1:1", 15*time.Minute) // classifier down -> a handoff to close
	ref1, _ := demoRefs(t)
	ctx := context.Background()
	out, err := o.HandleMessage(ctx, customer(ref1), contract.ChatRequest{Message: "No reconozco un cobro de 70 dólares", Lang: "es"}, "system")
	if err != nil || out.HandoffID == nil {
		t.Fatalf("handoff not created: %v %+v", err, out)
	}
	id := *out.HandoffID
	agent := auth.Principal{Username: "agente01", Roles: []string{"agent"}, ACR: 1}
	other := auth.Principal{Username: "agente02", Roles: []string{"agent"}, ACR: 1}
	note := contract.CloseRequest{Outcome: "rejected", Note: "El cliente reconoció el cargo por teléfono."}

	if _, err := o.CloseHandoff(ctx, agent, id, note); !errors.Is(err, ErrNotFound) {
		t.Errorf("closing an unclaimed handoff: got %v, want ErrNotFound", err)
	}
	if _, err := o.ClaimHandoff(ctx, agent, id); err != nil {
		t.Fatal(err)
	}
	if _, err := o.CloseHandoff(ctx, other, id, note); !errors.Is(err, ErrNotFound) {
		t.Errorf("closing someone else's handoff: got %v, want ErrNotFound", err)
	}
	if _, err := o.CloseHandoff(ctx, agent, id, contract.CloseRequest{Outcome: "maybe", Note: "x"}); !errors.Is(err, ErrBadRequest) {
		t.Errorf("invalid outcome: got %v, want ErrBadRequest", err)
	}
	h, err := o.CloseHandoff(ctx, agent, id, note)
	if err != nil {
		t.Fatal(err)
	}
	if h.Status != "closed" || h.Resolution == nil || h.Resolution.Outcome != "rejected" || h.Resolution.ClosedBy != "agente01" {
		t.Errorf("closed handoff: %+v", h)
	}

	mine, err := o.MyDisputes(ctx, customer(ref1))
	if err != nil {
		t.Fatal(err)
	}
	i := slices.IndexFunc(mine, func(d contract.MyDispute) bool { return d.ID == id })
	if i < 0 || mine[i].Status != "closed" || mine[i].Resolution == nil || mine[i].Resolution.Outcome != "rejected" {
		t.Errorf("customer view of the closed handoff: found=%v %+v", i >= 0, mine)
	}
}

func TestAbstainedOutOfScopeAsksInsteadOfRefusing(t *testing.T) {
	o := newOrchestrator(t, mlStub(t, `{"label":"out_of_scope","confidence":0.3,"abstain":true,"model_version":"stub"}`), 15*time.Minute)
	ref1, _ := demoRefs(t)
	out, err := o.HandleMessage(context.Background(), customer(ref1), contract.ChatRequest{Message: "tengo una duda", Lang: "es"}, "system")
	if err != nil {
		t.Fatal(err)
	}
	if out.Outcome != "clarify" || !slices.Contains(out.RuleIDs, "CLARIFY-TYPE") {
		t.Errorf("got outcome=%s rules=%v, want clarify CLARIFY-TYPE", out.Outcome, out.RuleIDs)
	}
}

// refusingModel is the fake provider, except that its extraction flags every message as another person's data.
type refusingModel struct{ llm.Fake }

func (refusingModel) Extract(ctx context.Context, text, lang string, today time.Time) (llm.Extraction, llm.Usage, error) {
	ex, u, err := llm.Fake{}.Extract(ctx, text, lang, today)
	ex.Refuse = "third_party_data"
	return ex, u, err
}

func TestRefusalScreenRefusesWhateverTheType(t *testing.T) {
	o := newOrchestrator(t, mlStub(t, `{"label":"unrecognized_charge","confidence":0.9,"abstain":false,"model_version":"stub"}`), 15*time.Minute)
	o.LLM = refusingModel{}
	ref1, _ := demoRefs(t)
	out, err := o.HandleMessage(context.Background(), customer(ref1), contract.ChatRequest{Message: "quiero ver los movimientos de mi papá", Lang: "es"}, "system")
	if err != nil {
		t.Fatal(err)
	}
	if out.Outcome != "abstain" || !slices.Contains(out.RuleIDs, "SEC-INJ-01") || out.PendingAction != nil {
		t.Errorf("got outcome=%s rules=%v pending=%v, want abstain SEC-INJ-01 and no action", out.Outcome, out.RuleIDs, out.PendingAction)
	}
}

// typedModel is the fake provider, except that its extraction reads every message as the given dispute type.
type typedModel struct {
	llm.Fake
	dtype string
}

func (m typedModel) Extract(ctx context.Context, text, lang string, today time.Time) (llm.Extraction, llm.Usage, error) {
	ex, u, err := llm.Fake{}.Extract(ctx, text, lang, today)
	ex.DisputeType = m.dtype
	return ex, u, err
}

func TestUnsureClassifierActsOnlyWhenTheModelAgrees(t *testing.T) {
	ref1, _ := demoRefs(t)
	unsure := `{"label":"wrong_amount","confidence":0.45,"abstain":true,"model_version":"stub"}`
	for _, tc := range []struct {
		model    string
		wantType bool
	}{{"wrong_amount", true}, {"unrecognized_charge", false}, {"", false}} {
		o := newOrchestrator(t, mlStub(t, unsure), 15*time.Minute)
		o.LLM = typedModel{dtype: tc.model}
		out, err := o.HandleMessage(context.Background(), customer(ref1), contract.ChatRequest{Message: "me cobraron otro valor", Lang: "es"}, "system")
		if err != nil {
			t.Fatal(err)
		}
		asked := out.Outcome == "clarify" && slices.Contains(out.RuleIDs, "CLARIFY-TYPE")
		if asked == tc.wantType {
			t.Errorf("model %q: outcome=%s rules=%v; want type set=%t", tc.model, out.Outcome, out.RuleIDs, tc.wantType)
		}
	}
}
