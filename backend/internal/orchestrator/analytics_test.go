package orchestrator

import (
	"testing"
	"time"
)

func TestParseRange(t *testing.T) {
	now := time.Date(2026, 10, 1, 12, 0, 0, 0, time.UTC)
	cases := []struct {
		in, name, bucket string
		from             *time.Time
		ok               bool
	}{
		{"", "24h", "hour", ptr(now.Add(-24 * time.Hour)), true},
		{"24h", "24h", "hour", ptr(now.Add(-24 * time.Hour)), true},
		{"7d", "7d", "day", ptr(now.AddDate(0, 0, -7)), true},
		{"30d", "30d", "day", ptr(now.AddDate(0, 0, -30)), true},
		{"all", "all", "day", nil, true},
		{"1y", "", "", nil, false},
		{"24h; DROP TABLE handoffs", "", "", nil, false},
	}
	for _, c := range cases {
		name, from, bucket, ok := ParseRange(c.in, now)
		if ok != c.ok || name != c.name || bucket != c.bucket || !sameTime(from, c.from) {
			t.Errorf("ParseRange(%q) = %q, %v, %q, %t", c.in, name, from, bucket, ok)
		}
	}
}

func ptr(t time.Time) *time.Time { return &t }

func sameTime(a, b *time.Time) bool {
	if a == nil || b == nil {
		return a == b
	}
	return a.Equal(*b)
}
