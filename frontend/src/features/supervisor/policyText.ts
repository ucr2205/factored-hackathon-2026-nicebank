// Plain-language (es/pt) reading of the active policy (policies/disputes.yaml) for supervisors. The YAML stays the
// source of truth; this only explains what each setting means for the conversation.
import type { AdminConfig, PolicyDisputeType, PolicyRule, PolicyStatusRule } from "../../api/types";
import { LOCALES, type Lang } from "../../app/i18n";
import { DISPUTE_TYPES, queueLabel, REASONS } from "../console/labels";

const ACTIONS: Record<Lang, Record<string, string>> = {
  es: { open_dispute_case: "Abre la disputa", block_card: "Bloquea la tarjeta" },
  pt: { open_dispute_case: "Abre a contestação", block_card: "Bloqueia o cartão" },
};

const TXN_STATUS: Record<Lang, Record<string, string>> = {
  es: { Approved: "aprobados", Pending: "pendientes" },
  pt: { Approved: "aprovadas", Pending: "pendentes" },
};

const NEVER: Record<Lang, Record<string, string>> = {
  es: { refund: "hacer reembolsos", transfer_funds: "mover o transferir dinero", reveal_other_customer_data: "mostrar datos de otro cliente" },
  pt: { refund: "fazer reembolsos", transfer_funds: "mover ou transferir dinheiro", reveal_other_customer_data: "mostrar dados de outro cliente" },
};

const STATUS_TEXT: Record<Lang, Record<string, string>> = {
  es: {
    Reversed: "Si el cargo ya fue revertido, le explica al cliente que el dinero volvió y no abre una disputa.",
    Declined: "Si la compra fue rechazada, le explica que no se le cobró nada y no abre una disputa.",
    Pending: "Si el cargo sigue pendiente, le explica que todavía puede cambiar y que vuelva cuando se confirme.",
  },
  pt: {
    Reversed: "Se a cobrança já foi estornada, explica ao cliente que o dinheiro voltou e não abre uma contestação.",
    Declined: "Se a compra foi recusada, explica que nada foi cobrado e não abre uma contestação.",
    Pending: "Se a cobrança ainda está pendente, explica que ela ainda pode mudar e que o cliente volte quando for confirmada.",
  },
};

// Sentence pieces, kept together per language so word order can differ.
const W = {
  es: {
    withConfirm: "con confirmación del cliente",
    withStepUp: "y código de verificación",
    neverAlone: "Nunca lo cierra solo: siempre participa un especialista",
    upTo: (v: string) => `hasta ${v}`,
    lastDays: (n: number) => `cargos de los últimos ${n} días`,
    onlyStatuses: (s: string[]) => `solo movimientos ${s.join(" o ")}`,
    always: "Siempre",
    alwaysTo: (queue: string, reason: string) => `Siempre pasa al equipo de ${queue} (${reason})`,
    over: (v: string) => `Más de ${v}`,
    otherwise: "Si no aplica",
    proposeBlock: " y propone bloquear la tarjeta",
    goesTo: (when: string, queue: string, suggestion: string) => `${when}: pasa al equipo de ${queue}${suggestion}`,
    ineligible: (n: number) => `Más de ${n} días o estado no válido: pasa al equipo de Disputas`,
    onlyIn: (types: string) => ` (solo en: ${types})`,
    aSpecialist: "un especialista",
    declinedFraud: (scope: string, who: string) =>
      `Si alguien intentó una compra que el cliente no reconoce y fue rechazada${scope}: le explica que no se le cobró nada, pero propone bloquear la tarjeta y pasa el caso al equipo de ${who}.`,
    lastJoin: "ni",
    never: (list: string) => `Nunca puede ${list}.`,
    confirmAll: "Ninguna acción se ejecuta sin que el cliente la confirme.",
    stepUp: "Bloquear una tarjeta exige además el código de la app autenticadora.",
    usd: "Todo monto se evalúa en USD con la tasa de cambio del día del movimiento. El cliente y el agente ven el monto en su moneda, su equivalente en USD y la tasa usada.",
    idle: (n: number) => `La conversación se cierra tras ${n} minutos sin actividad.`,
  },
  pt: {
    withConfirm: "com confirmação do cliente",
    withStepUp: "e código de verificação",
    neverAlone: "Nunca encerra sozinho: sempre participa um especialista",
    upTo: (v: string) => `até ${v}`,
    lastDays: (n: number) => `cobranças dos últimos ${n} dias`,
    onlyStatuses: (s: string[]) => `somente movimentações ${s.join(" ou ")}`,
    always: "Sempre",
    alwaysTo: (queue: string, reason: string) => `Sempre passa para a equipe de ${queue} (${reason})`,
    over: (v: string) => `Mais de ${v}`,
    otherwise: "Se não se aplicar",
    proposeBlock: " e propõe bloquear o cartão",
    goesTo: (when: string, queue: string, suggestion: string) => `${when}: passa para a equipe de ${queue}${suggestion}`,
    ineligible: (n: number) => `Mais de ${n} dias ou status inválido: passa para a equipe de Contestações`,
    onlyIn: (types: string) => ` (somente em: ${types})`,
    aSpecialist: "um especialista",
    declinedFraud: (scope: string, who: string) =>
      `Se alguém tentou uma compra que o cliente não reconhece e ela foi recusada${scope}: explica que nada foi cobrado, mas propõe bloquear o cartão e passa o caso para a equipe de ${who}.`,
    lastJoin: "nem",
    never: (list: string) => `Nunca pode ${list}.`,
    confirmAll: "Nenhuma ação é executada sem que o cliente a confirme.",
    stepUp: "Bloquear um cartão exige também o código do app autenticador.",
    usd: "Todo valor é avaliado em USD com a taxa de câmbio do dia da movimentação. O cliente e o agente veem o valor na moeda original, o equivalente em USD e a taxa usada.",
    idle: (n: number) => `A conversa é encerrada após ${n} minutos sem atividade.`,
  },
} as const;

const usd = (v: number, lang: Lang) => `${new Intl.NumberFormat(LOCALES[lang], { useGrouping: "always" }).format(v)} USD`;

/** "a, b ni c" / "a, b nem c" */
const listNi = (items: string[], lang: Lang) =>
  items.length > 1 ? `${items.slice(0, -1).join(", ")} ${W[lang].lastJoin} ${items[items.length - 1]}` : items.join("");

/** What the assistant does on its own for this dispute type, with the safeguards that apply. */
export function autoActionText(d: PolicyDisputeType, c: AdminConfig, lang: Lang): string {
  const g = c.policy.globals;
  const extras: string[] = [];
  if (g.confirm_actions.includes(d.auto_action)) extras.push(W[lang].withConfirm);
  if (g.step_up_actions.includes(d.auto_action)) extras.push(W[lang].withStepUp);
  return `${ACTIONS[lang][d.auto_action] ?? d.auto_action}${extras.length ? ` (${extras.join(" ")})` : ""}`;
}

/** When the assistant can resolve it alone. */
export function conditionText(d: PolicyDisputeType, lang: Lang): string {
  const w = W[lang];
  if (d.always_escalate) return w.neverAlone;
  const parts: string[] = [];
  if (d.max_auto_amount_usd) parts.push(w.upTo(usd(d.max_auto_amount_usd, lang)));
  if (d.eligible_if.max_age_days) parts.push(w.lastDays(d.eligible_if.max_age_days));
  const statuses = d.eligible_if.transaction_status?.map((s) => TXN_STATUS[lang][s] ?? s);
  if (statuses?.length) parts.push(w.onlyStatuses(statuses));
  return parts.length ? parts.join(" · ") : w.always;
}

/** What happens when it cannot resolve it alone, one line per situation. */
export function escalationLines(d: PolicyDisputeType, lang: Lang): string[] {
  const w = W[lang];
  if (d.always_escalate) {
    return [w.alwaysTo(queueLabel(d.always_escalate.queue, lang), REASONS[lang][d.always_escalate.reason] ?? d.always_escalate.reason)];
  }
  const lines = (d.escalate_if ?? []).map((e) => {
    const when = e.condition === "amount_over_max" && d.max_auto_amount_usd ? w.over(usd(d.max_auto_amount_usd, lang)) : w.otherwise;
    const suggestion = e.suggest_action === "block_card" ? w.proposeBlock : "";
    return w.goesTo(when, queueLabel(e.queue, lang), suggestion);
  });
  // Out-of-window or wrong-status charges always go to the disputes team (policy.Evaluate, "ineligible").
  if (d.eligible_if.max_age_days) lines.push(w.ineligible(d.eligible_if.max_age_days));
  return lines;
}

/** Distinct rule ids behind a dispute type (auto, escalations, ineligible), for the technical view. */
export const escalationRuleIds = (d: PolicyDisputeType) =>
  [d.rules?.auto, d.always_escalate?.rule_id, ...(d.escalate_if?.map((e) => e.rule_id) ?? []), d.rules?.ineligible]
    .filter((r, i, all): r is string => !!r && all.indexOf(r) === i);

/** Global rules as sentences; unknown rules fall back to the policy's own description. */
export function globalRuleText(r: PolicyRule, c: AdminConfig, lang: Lang): string {
  const g = c.policy.globals;
  const known: Record<Lang, Record<string, string>> = {
    es: {
      "SCOPE-01": "Si piden algo que no es una disputa de tarjeta (préstamos, inversiones, cambios de datos), explica qué sí puede hacer y no continúa.",
      "SEC-INJ-01": "Si el mensaje intenta cambiar las instrucciones del asistente o pedir acciones prohibidas, lo bloquea y no hace nada.",
      "CLARIFY-TYPE": "Si no está claro qué pasó con el cargo, pregunta en vez de adivinar.",
      "CLARIFY-NOTFOUND": "Si no encuentra el movimiento, dice qué buscó y pide fecha, monto o comercio.",
      "CLARIFY-MULTI": `Si varios movimientos coinciden, muestra hasta ${g.max_candidates_shown} y el cliente elige.`,
      "ESC-CLARIFY-LIMIT": `Si después de ${g.max_clarifications} aclaraciones no logra identificar el movimiento, pasa el caso a un especialista.`,
      "DISP-DUPCASE-01": "Si el movimiento ya tiene una disputa abierta, la informa y no crea otra.",
      "ESC-TECH-01": "Si falla algo técnico, pasa el caso a un especialista en vez de dejar al cliente sin respuesta.",
    },
    pt: {
      "SCOPE-01": "Se pedirem algo que não é uma contestação de cartão (empréstimos, investimentos, alteração de dados), explica o que pode fazer e não continua.",
      "SEC-INJ-01": "Se a mensagem tentar mudar as instruções do assistente ou pedir ações proibidas, bloqueia a mensagem e não faz nada.",
      "CLARIFY-TYPE": "Se não estiver claro o que aconteceu com a cobrança, pergunta em vez de adivinhar.",
      "CLARIFY-NOTFOUND": "Se não encontrar a movimentação, diz o que buscou e pede data, valor ou estabelecimento.",
      "CLARIFY-MULTI": `Se várias movimentações coincidirem, mostra até ${g.max_candidates_shown} e o cliente escolhe.`,
      "ESC-CLARIFY-LIMIT": `Se depois de ${g.max_clarifications} esclarecimentos não conseguir identificar a movimentação, passa o caso para um especialista.`,
      "DISP-DUPCASE-01": "Se a movimentação já tiver uma contestação aberta, informa isso e não cria outra.",
      "ESC-TECH-01": "Se algo técnico falhar, passa o caso para um especialista em vez de deixar o cliente sem resposta.",
    },
  };
  return known[lang][r.rule_id] ?? r.description;
}

/** "Before opening a dispute" rules (policy explain_status) as sentences. */
export function statusRuleText(r: PolicyStatusRule, lang: Lang): string {
  const w = W[lang];
  const scope = r.types?.length ? w.onlyIn(r.types.map((t) => (DISPUTE_TYPES[lang][t] ?? t).toLowerCase()).join(", ")) : "";
  if (r.suggest_action === "block_card") {
    const who = r.queue ? queueLabel(r.queue, lang) : w.aSpecialist;
    return w.declinedFraud(scope, who);
  }
  const base = STATUS_TEXT[lang][r.status] ?? r.description;
  return scope ? base.replace(/\.$/, `${scope}.`) : base;
}

/** Guarantees that hold in every conversation, from the policy's global settings. */
export function guarantees(c: AdminConfig, lang: Lang): string[] {
  const g = c.policy.globals;
  const w = W[lang];
  const out = [];
  if (g.never?.length) out.push(w.never(listNi(g.never.map((n) => NEVER[lang][n] ?? n), lang)));
  if (g.confirm_actions?.length) out.push(w.confirmAll);
  if (g.step_up_actions?.includes("block_card")) out.push(w.stepUp);
  out.push(w.usd);
  if (g.session_idle_minutes) out.push(w.idle(g.session_idle_minutes));
  return out;
}

/** Friendly names for the technical components shown in the active configuration. */
export function modelLabel(provider: string, version: string, lang: Lang): { name: string; detail: string } {
  if (provider === "fake") {
    return lang === "pt"
      ? { name: "Simulado (regras e templates)", detail: "Sem IA externa: grátis e previsível, para testes" }
      : { name: "Simulado (reglas y plantillas)", detail: "Sin IA externa: gratis y predecible, para pruebas" };
  }
  const model = version.split("/")[0];
  const names: Record<string, string> = { "deepseek-flash": "DeepSeek Flash", "deepseek-v4-flash": "DeepSeek Flash", "deepseek-v4-pro": "DeepSeek Pro" };
  return {
    name: names[model] ?? model,
    detail: lang === "pt" ? "Só entende a mensagem e redige; não decide nem executa ações" : "Solo entiende el mensaje y redacta; no decide ni ejecuta acciones",
  };
}

/** Friendly name for the ml-service classifier model (keyword stub, trained model or unavailable). */
export function classifierLabel(model: string, lang: Lang): { name: string; detail: string } {
  const pt = lang === "pt";
  if (model === "unavailable") {
    return pt
      ? { name: "Indisponível", detail: "O serviço de classificação não responde" }
      : { name: "No disponible", detail: "El servicio de clasificación no responde" };
  }
  if (model.startsWith("keyword-stub")) {
    return pt
      ? { name: "Palavras-chave (provisório)", detail: "Será substituído pelo modelo treinado" }
      : { name: "Palabras clave (provisional)", detail: "Se reemplazará por el modelo entrenado" };
  }
  return { name: model, detail: pt ? "Modelo treinado que identifica o tipo de caso" : "Modelo entrenado que identifica el tipo de caso" };
}

/** Explains a team_generated policy origin; any other origin is shown as is. */
export function originLabel(origin: string, lang: Lang): string {
  if (!origin.startsWith("team_generated")) return origin;
  return lang === "pt"
    ? "Política de exemplo criada pela equipe para o hackathon; não é a política de um banco real."
    : "Política de ejemplo creada por el equipo para el hackathon; no es la política de un banco real.";
}
