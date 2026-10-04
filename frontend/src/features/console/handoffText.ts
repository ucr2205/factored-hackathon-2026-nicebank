// Portuguese view of the backend-generated handoff text (contract C5). The backend writes open questions and
// verified facts in Spanish from fixed templates (backend/internal/orchestrator/handoff.go); for a Portuguese UI
// these helpers swap in the known questions and rewrite the known fact templates, keeping every value verbatim.
// Anything unknown is shown exactly as the backend sent it.
import type { Handoff } from "../../api/types";
import type { Lang } from "../../app/i18n";

// Mirrors handoff.go `openQuestions` (fixed per reason).
const OPEN_QUESTIONS_PT: Record<string, string[]> = {
  possible_fraud_high_amount: [
    "O cliente ainda está com o cartão físico?",
    "Há outras movimentações que ele não reconhece?",
    "Deve ser emitido um cartão de reposição?",
  ],
  card_lost_or_stolen: [
    "Quando e onde o cartão foi perdido?",
    "Houve movimentações depois da perda?",
    "Confirmar o endereço de entrega do novo cartão.",
  ],
  outside_automatic_window: [
    "Por que a contestação foi feita fora do prazo automático?",
    "O cliente tem comprovantes ou comunicação com o estabelecimento?",
  ],
  could_not_identify_transaction: ["Qual movimentação o cliente quer contestar (data, valor, estabelecimento)?"],
  technical_failure: ["Repetir a etapa que falhou e confirmar o resultado com o cliente."],
  action_not_verified: ["Verificar manualmente se a ação foi aplicada antes de informar o cliente."],
  high_amount_duplicate: ["O estabelecimento já emitiu um estorno?", "O cliente tem o comprovante das duas cobranças?"],
  high_amount_dispute: ["O cliente tem comprovante ou comunicação com o estabelecimento?"],
  declined_unrecognized_attempt: [
    "Houve outras tentativas recusadas ou aprovadas que o cliente não reconhece?",
    "Onde o cartão pode ter sido exposto (compras on-line, perda)?",
    "Deve ser emitido um cartão de reposição?",
  ],
};

/** Open questions in the UI language: the Portuguese set for a known reason, otherwise the payload's list. */
export function openQuestions(h: Handoff, lang: Lang): string[] {
  if (lang === "pt" && OPEN_QUESTIONS_PT[h.reason]) return OPEN_QUESTIONS_PT[h.reason];
  return h.open_questions ?? [];
}

// Anchored rewrites of the Spanish fact templates; only template words change, captured values stay verbatim.
const FACTS_PT: [RegExp, (m: RegExpMatchArray) => string][] = [
  // "Movimiento %s: %s en %s el %s (%s), tarjeta terminada en %s, estado %s"
  [/^Movimiento (\S+): (.+?) en (.*) el (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \((.*)\), tarjeta terminada en (\S+), estado (.*)$/, (m) =>
    `Movimentação ${m[1]}: ${m[2]} em ${m[3]} no dia ${m[4]} (${m[5]}), cartão com final ${m[6]}, status ${m[7]}`],
  // staffAmount, USD: "Monto: %s (sin conversión)"
  [/^Monto: (.+) \(sin conversión\)$/, (m) => `Valor: ${m[1]} (sem conversão)`],
  // staffAmount, no rate: "Monto: %s = %s (equivalente del dataset, sin tasa del día)"
  [/^Monto: (.+?) = (.+) \(equivalente del dataset, sin tasa del día\)$/, (m) => `Valor: ${m[1]} = ${m[2]} (equivalente do dataset, sem taxa do dia)`],
  // staffAmount: "Monto: %s = %s · tasa 1 USD = %s (1 %s = %s USD) del dd/mm/yyyy"
  [/^Monto: (.+?) = (.+?) · tasa 1 USD = (.+?) \((1 \S+ = \S+ USD)\) del (\d{2}\/\d{2}\/\d{4})$/, (m) =>
    `Valor: ${m[1]} = ${m[2]} · taxa 1 USD = ${m[3]} (${m[4]}) de ${m[5]}`],
  // "Acción %s aplicada y verificada (%s)"
  [/^Acción (\S+) aplicada y verificada \((.*)\)$/, (m) => `Ação ${m[1]} aplicada e verificada (${m[2]})`],
];

/** A verified fact in the UI language; the original text when lang is es or no known template matches. */
export function factText(fact: string, lang: Lang): string {
  if (lang !== "pt") return fact;
  for (const [re, fmt] of FACTS_PT) {
    const m = fact.match(re);
    if (m) return fmt(m);
  }
  return fact;
}
