// Package guard masks personal data before text leaves the service and flags prompt-injection attempts.
// Injection detection is defense in depth: even undetected, a message cannot trigger tools, because only
// the orchestrator executes actions and only after policy checks and customer confirmation.
package guard

import (
	"regexp"

	"github.com/factored-hackathon-2026/disputes/backend/internal/textnorm"
)

var (
	emailRe = regexp.MustCompile(`[\w.+-]+@[\w-]+\.[\w.-]+`)
	// A number right after a document, account or phone keyword is personal data at any length, even with
	// dots (DNI 12.345.678). Without a keyword, 8+ characters: shorter runs are usually amounts or dates the
	// extractor needs.
	labeledNum = regexp.MustCompile(`(?i)\b(dni|c[eé]dula|cc|cpf|rg|cuit|cuil|curp|rfc|documento|pasaporte|passaporte|` +
		`cuenta|conta|clabe|cbu|tel[eé]fono|telefone|celular|whatsapp)` +
		`((?:\W{1,3}(?:es|é|e|de|do|da|mi|meu|minha|nro\.?|no\.?|n[°º]|n[uú]mero))*\W{1,3})\d[\d .-]{3,}\d`)
	cpfRe   = regexp.MustCompile(`\b\d{3}\.\d{3}\.\d{3}-\d{2}\b`)
	longNum = regexp.MustCompile(`\b\d[\d -]{6,}\d\b`) // card, account, document and phone numbers
	// Matched against accent-free lowercase text (see textnorm.Normalize).
	injectRe = regexp.MustCompile(`(ignor[ae]\w*\s+(todas?\s+)?(las|as|the|tus|suas|previous|anteriores|instrucciones|instrucoes|instructions)` +
		`|system prompt|prompt del sistema|prompt do sistema|eres ahora|voce agora e|you are now|actua como|modo desarrollador|developer mode` +
		`|reembols\w*|devuelve (el|mi) dinero|transfiere\w*|transfira|estorn\w*|revela\w*|mostra\w* (os )?dados de outro|datos de otro cliente)`)
)

// Mask replaces emails, long digit sequences and the given names with placeholders.
func Mask(text string, names ...string) string {
	out := emailRe.ReplaceAllString(text, "[EMAIL]")
	out = labeledNum.ReplaceAllString(out, "${1}${2}[NUMBER]")
	out = cpfRe.ReplaceAllString(out, "[NUMBER]")
	out = longNum.ReplaceAllString(out, "[NUMBER]")
	for _, n := range names {
		if len(n) >= 3 {
			out = regexp.MustCompile(`(?i)\b`+regexp.QuoteMeta(n)+`\b`).ReplaceAllString(out, "[NAME]")
		}
	}
	return out
}

// LooksLikeInjection reports whether the text tries to override instructions or request forbidden actions.
func LooksLikeInjection(text string) bool {
	return injectRe.MatchString(textnorm.Normalize(text))
}
