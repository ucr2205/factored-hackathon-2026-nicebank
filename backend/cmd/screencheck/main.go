// Command screencheck measures the refusal screen (the "refuse" field of the DeepSeek extraction) on a labeled file:
// how many "refuse" messages it flags (recall) and how many "allow" messages it wrongly flags (false refusals).
// Messages are masked exactly as the backend masks them before they reach the model.
//
//	cd backend && DEEPSEEK_API_KEY=... go run ./cmd/screencheck -file ../eval/screen/dev.jsonl [-v]
//
// Input lines: {"id": "...", "lang": "es"|"pt", "label": "refuse"|"allow", "kind": "...", "text": "..."}.
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
)

type row struct {
	ID, Lang, Label, Kind, Text string
	Got                         string `json:"-"`
	Regex                       bool   `json:"-"`
}

func main() {
	file := flag.String("file", "../eval/screen/dev.jsonl", "labeled jsonl file")
	model := flag.String("model", "deepseek-flash", "DeepSeek model")
	verbose := flag.Bool("v", false, "print every error")
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
		if err := json.Unmarshal(sc.Bytes(), &r); err == nil && r.Text != "" {
			rows = append(rows, &r)
		}
	}
	f.Close()

	d := llm.NewDeepSeek("https://api.deepseek.com", key, *model, "", false)
	today := time.Date(2026, 6, 17, 0, 0, 0, 0, time.UTC)
	var wg sync.WaitGroup
	var mu sync.Mutex
	var cost float64
	sem := make(chan struct{}, 8)
	for _, r := range rows {
		wg.Add(1)
		go func(r *row) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			r.Regex = guard.LooksLikeInjection(r.Text)
			ex, u, _ := d.Extract(context.Background(), guard.Mask(r.Text), r.Lang, today)
			r.Got = ex.Refuse
			mu.Lock()
			cost += u.CostUSD
			mu.Unlock()
		}(r)
	}
	wg.Wait()

	// The backend refuses when either the regex guard or the screen fires; report both and the combination.
	type tally struct{ n, screen, regex, either int }
	byKind := map[string]*tally{}
	total := map[string]*tally{"refuse": {}, "allow": {}}
	for _, r := range rows {
		k := byKind[r.Label+"/"+r.Kind]
		if k == nil {
			k = &tally{}
			byKind[r.Label+"/"+r.Kind] = k
		}
		for _, t := range []*tally{k, total[r.Label]} {
			t.n++
			if r.Got != "" {
				t.screen++
			}
			if r.Regex {
				t.regex++
			}
			if r.Got != "" || r.Regex {
				t.either++
			}
		}
	}
	fmt.Printf("%s with %s (cost USD %.4f)\n", *file, *model, cost)
	fmt.Printf("refuse flagged: screen %d/%d, regex %d/%d, either %d/%d\n", total["refuse"].screen, total["refuse"].n,
		total["refuse"].regex, total["refuse"].n, total["refuse"].either, total["refuse"].n)
	fmt.Printf("allow wrongly flagged (false refusals): screen %d/%d, regex %d/%d, either %d/%d\n", total["allow"].screen,
		total["allow"].n, total["allow"].regex, total["allow"].n, total["allow"].either, total["allow"].n)
	kinds := make([]string, 0, len(byKind))
	for k := range byKind {
		kinds = append(kinds, k)
	}
	sort.Strings(kinds)
	for _, k := range kinds {
		t := byKind[k]
		fmt.Printf("  %-40s flagged %d/%d (screen %d, regex %d)\n", k, t.either, t.n, t.screen, t.regex)
	}
	if *verbose {
		for _, r := range rows {
			flagged := r.Got != "" || r.Regex
			if flagged != (r.Label == "refuse") {
				fmt.Printf("  ERROR %s %s/%s got=%q regex=%t: %s\n", r.ID, r.Label, r.Kind, r.Got, r.Regex, r.Text)
			}
		}
	}
}
