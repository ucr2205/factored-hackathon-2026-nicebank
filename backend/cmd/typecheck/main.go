// Command typecheck measures how the dispute type is decided on a labeled file, with the live ml-service classifier
// and the DeepSeek extraction ("dispute_type"), under three rules:
//
//	classifier   the type is set only when the classifier is confident (no abstention)
//	agreement    also when the classifier abstains but its best guess equals the model's reading (served rule)
//	llm-fallback also when the classifier abstains and the model names any type (reference only, not served)
//
// For each rule it counts decisions with the right type, decisions with a WRONG type (the dangerous outcome: wrong
// deadlines and amount limits) and messages where the assistant would ask instead.
//
//	cd backend && DEEPSEEK_API_KEY=... go run ./cmd/typecheck -file ../eval/typecheck/holdout.jsonl [-v]
//
// Input lines: {"id": "...", "lang": "es"|"pt", "label": "<taxonomy C6 label>", "text": "..."}.
//
// Pipeline role: offline measurement of how Understand sets the dispute type, which then drives Decide (policy).
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"sync"
	"time"

	"github.com/factored-hackathon-2026/disputes/backend/internal/guard"
	"github.com/factored-hackathon-2026/disputes/backend/internal/llm"
	"github.com/factored-hackathon-2026/disputes/backend/internal/mlclient"
)

type row struct {
	ID, Lang, Label, Text string
	cls                   mlclient.Classification
	llmType, refuse       string
}

var rules = []string{"classifier", "agreement", "llm-fallback"}

// decide returns the dispute type the rule sets, "out_of_scope" for a confident out-of-scope, or "" (ask / refuse).
func decide(rule string, r *row) string {
	if r.refuse != "" {
		return ""
	}
	if r.cls.Label == "out_of_scope" && !r.cls.Abstain {
		return "out_of_scope"
	}
	known := llm.DisputeTypes[r.cls.Label]
	switch {
	case known && !r.cls.Abstain:
		return r.cls.Label
	case rule == "agreement" && known && r.llmType == r.cls.Label:
		return r.cls.Label
	case rule == "llm-fallback" && r.llmType != "":
		return r.llmType
	}
	return ""
}

func main() {
	file := flag.String("file", "../eval/typecheck/holdout.jsonl", "labeled jsonl file")
	mlURL := flag.String("ml", "http://127.0.0.1:8000", "ml-service URL")
	verbose := flag.Bool("v", false, "print wrong decisions and the agreement rule's questions")
	flag.Parse()
	key := os.Getenv("DEEPSEEK_API_KEY")
	if key == "" {
		fmt.Fprintln(os.Stderr, "DEEPSEEK_API_KEY is not set")
		os.Exit(2)
	}
	f, err := os.Open(*file)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	var rows []*row
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		var r row
		if json.Unmarshal(sc.Bytes(), &r) == nil && r.Text != "" {
			rows = append(rows, &r)
		}
	}
	f.Close()

	ml := mlclient.New(*mlURL)
	d := llm.NewDeepSeek("https://api.deepseek.com", key, "deepseek-flash", "", false)
	today := time.Date(2026, 6, 17, 0, 0, 0, 0, time.UTC)
	var wg sync.WaitGroup
	sem := make(chan struct{}, 6)
	failed := 0
	var mu sync.Mutex
	for _, r := range rows {
		wg.Add(1)
		go func(r *row) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			masked := guard.Mask(r.Text)
			cls, err := ml.Classify(context.Background(), masked, r.Lang)
			if err != nil {
				mu.Lock()
				failed++
				mu.Unlock()
				return
			}
			ex, _, _ := d.Extract(context.Background(), masked, r.Lang, "", today)
			r.cls, r.llmType, r.refuse = cls, ex.DisputeType, ex.Refuse
		}(r)
	}
	wg.Wait()
	if failed > 0 {
		fmt.Fprintf(os.Stderr, "%d classifier calls failed\n", failed)
	}

	type tally struct{ n, right, wrong, ask int }
	for _, rule := range rules {
		total := tally{}
		byLabel := map[string]*tally{}
		for _, r := range rows {
			got := decide(rule, r)
			t := byLabel[r.Label]
			if t == nil {
				t = &tally{}
				byLabel[r.Label] = t
			}
			for _, x := range []*tally{t, &total} {
				x.n++
				switch {
				case r.Label == "other_in_scope" && got == "", got == r.Label:
					x.right++
				case got == "":
					x.ask++
				default:
					x.wrong++
				}
			}
		}
		fmt.Printf("%-13s right %3d/%d (%.1f%%)  wrong type %d  asks %d\n", rule, total.right, total.n,
			100*float64(total.right)/float64(total.n), total.wrong, total.ask)
		labels := make([]string, 0, len(byLabel))
		for l := range byLabel {
			labels = append(labels, l)
		}
		sort.Strings(labels)
		for _, l := range labels {
			t := byLabel[l]
			fmt.Printf("    %-24s right %2d/%-2d wrong %d asks %d\n", l, t.right, t.n, t.wrong, t.ask)
		}
	}
	if *verbose {
		for _, r := range rows {
			got := decide("agreement", r)
			if got != r.Label && !(r.Label == "other_in_scope" && got == "") {
				fmt.Printf("  %s %s -> %q (classifier %s %.2f abstain=%t, model %q, refuse %q): %s\n", r.ID, r.Label, got,
					r.cls.Label, r.cls.Confidence, r.cls.Abstain, r.llmType, r.refuse, r.Text)
			}
		}
	}
}
