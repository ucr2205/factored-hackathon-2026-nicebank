// Package textnorm normalizes customer text for matching: lowercase, accents removed.
// Shared by the guard, the tools, the fake model and the baseline router so matching behaves the same everywhere.
package textnorm

import (
	"strings"
	"unicode"

	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

// Normalize lowercases and strips accents so "miércoles" matches "miercoles".
func Normalize(s string) string {
	t := transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)
	out, _, _ := transform.String(t, strings.ToLower(s))
	return out
}
