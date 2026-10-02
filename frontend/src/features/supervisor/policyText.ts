// Plain-Spanish reading of the active policy (policies/disputes.yaml) for supervisors. The YAML stays the
// source of truth; this only explains what each setting means for the conversation.
import type { AdminConfig, PolicyDisputeType, PolicyRule, PolicyStatusRule } from "../../api/types";
import { DISPUTE_TYPES, queueLabel, REASONS } from "../console/labels";

const ACTIONS: Record<string, string> = {
  open_dispute_case: "Abre la disputa",
  block_card: "Bloquea la tarjeta",
};

const TXN_STATUS: Record<string, string> = { Approved: "aprobados", Pending: "pendientes" };

const NEVER: Record<string, string> = {
  refund: "hacer reembolsos",
  transfer_funds: "mover o transferir dinero",
  reveal_other_customer_data: "mostrar datos de otro cliente",
};

const usd = (v: number) => `${new Intl.NumberFormat("es", { useGrouping: "always" }).format(v)} USD`;

/** "a, b ni c" */
const listNi = (items: string[]) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} ni ${items[items.length - 1]}` : items.join(""));

/** What the assistant does on its own for this dispute type, with the safeguards that apply. */
export function autoActionText(d: PolicyDisputeType, c: AdminConfig): string {
  const g = c.policy.globals;
  const extras: string[] = [];
  if (g.confirm_actions.includes(d.auto_action)) extras.push("con confirmación del cliente");
  if (g.step_up_actions.includes(d.auto_action)) extras.push("y código de verificación");
  return `${ACTIONS[d.auto_action] ?? d.auto_action}${extras.length ? ` (${extras.join(" ")})` : ""}`;
}

/** When the assistant can resolve it alone. */
export function conditionText(d: PolicyDisputeType): string {
  if (d.always_escalate) return "Nunca lo cierra solo: siempre participa un especialista";
  const parts: string[] = [];
  if (d.max_auto_amount_usd) parts.push(`hasta ${usd(d.max_auto_amount_usd)}`);
  if (d.eligible_if.max_age_days) parts.push(`cargos de los últimos ${d.eligible_if.max_age_days} días`);
  const statuses = d.eligible_if.transaction_status?.map((s) => TXN_STATUS[s] ?? s);
  if (statuses?.length) parts.push(`solo movimientos ${statuses.join(" o ")}`);
  return parts.length ? parts.join(" · ") : "Siempre";
}

/** What happens when it cannot resolve it alone, one line per situation. */
export function escalationLines(d: PolicyDisputeType): string[] {
  if (d.always_escalate) {
    return [`Siempre pasa al equipo de ${queueLabel(d.always_escalate.queue)} (${REASONS[d.always_escalate.reason] ?? d.always_escalate.reason})`];
  }
  const lines = (d.escalate_if ?? []).map((e) => {
    const when = e.condition === "amount_over_max" && d.max_auto_amount_usd ? `Más de ${usd(d.max_auto_amount_usd)}` : "Si no aplica";
    const suggestion = e.suggest_action === "block_card" ? " y propone bloquear la tarjeta" : "";
    return `${when}: pasa al equipo de ${queueLabel(e.queue)}${suggestion}`;
  });
  // Out-of-window or wrong-status charges always go to the disputes team (policy.Evaluate, "ineligible").
  if (d.eligible_if.max_age_days) lines.push(`Más de ${d.eligible_if.max_age_days} días o estado no válido: pasa al equipo de Disputas`);
  return lines;
}

/** Distinct rule ids behind a dispute type (auto, escalations, ineligible), for the technical view. */
export const escalationRuleIds = (d: PolicyDisputeType) =>
  [d.rules?.auto, d.always_escalate?.rule_id, ...(d.escalate_if?.map((e) => e.rule_id) ?? []), d.rules?.ineligible]
    .filter((r, i, all): r is string => !!r && all.indexOf(r) === i);

/** Global rules as sentences; unknown rules fall back to the policy's own description. */
export function globalRuleText(r: PolicyRule, c: AdminConfig): string {
  const g = c.policy.globals;
  const known: Record<string, string> = {
    "SCOPE-01": "Si piden algo que no es una disputa de tarjeta (préstamos, inversiones, cambios de datos), explica qué sí puede hacer y no continúa.",
    "SEC-INJ-01": "Si el mensaje intenta cambiar las instrucciones del asistente o pedir acciones prohibidas, lo bloquea y no hace nada.",
    "CLARIFY-TYPE": "Si no está claro qué pasó con el cargo, pregunta en vez de adivinar.",
    "CLARIFY-NOTFOUND": "Si no encuentra el movimiento, dice qué buscó y pide fecha, monto o comercio.",
    "CLARIFY-MULTI": `Si varios movimientos coinciden, muestra hasta ${g.max_candidates_shown} y el cliente elige.`,
    "ESC-CLARIFY-LIMIT": `Si después de ${g.max_clarifications} aclaraciones no logra identificar el movimiento, pasa el caso a un especialista.`,
    "DISP-DUPCASE-01": "Si el movimiento ya tiene una disputa abierta, la informa y no crea otra.",
    "ESC-TECH-01": "Si falla algo técnico, pasa el caso a un especialista en vez de dejar al cliente sin respuesta.",
  };
  return known[r.rule_id] ?? r.description;
}

const STATUS_TEXT: Record<string, string> = {
  Reversed: "Si el cargo ya fue revertido, le explica al cliente que el dinero volvió y no abre una disputa.",
  Declined: "Si la compra fue rechazada, le explica que no se le cobró nada y no abre una disputa.",
  Pending: "Si el cargo sigue pendiente, le explica que todavía puede cambiar y que vuelva cuando se confirme.",
};

/** "Before opening a dispute" rules (policy explain_status) as sentences. */
export function statusRuleText(r: PolicyStatusRule): string {
  const scope = r.types?.length ? ` (solo en: ${r.types.map((t) => (DISPUTE_TYPES[t] ?? t).toLowerCase()).join(", ")})` : "";
  if (r.suggest_action === "block_card") {
    const who = r.queue ? queueLabel(r.queue) : "un especialista";
    return `Si alguien intentó una compra que el cliente no reconoce y fue rechazada${scope}: le explica que no se le cobró nada, pero propone bloquear la tarjeta y pasa el caso al equipo de ${who}.`;
  }
  const base = STATUS_TEXT[r.status] ?? r.description;
  return scope ? base.replace(/\.$/, `${scope}.`) : base;
}

/** Guarantees that hold in every conversation, from the policy's global settings. */
export function guarantees(c: AdminConfig): string[] {
  const g = c.policy.globals;
  const out = [];
  if (g.never?.length) out.push(`Nunca puede ${listNi(g.never.map((n) => NEVER[n] ?? n))}.`);
  if (g.confirm_actions?.length) out.push("Ninguna acción se ejecuta sin que el cliente la confirme.");
  if (g.step_up_actions?.includes("block_card")) out.push("Bloquear una tarjeta exige además el código de la app autenticadora.");
  out.push("Todo monto se evalúa en USD con la tasa de cambio del día del movimiento. El cliente y el agente ven el monto en su moneda, su equivalente en USD y la tasa usada.");
  if (g.session_idle_minutes) out.push(`La conversación se cierra tras ${g.session_idle_minutes} minutos sin actividad.`);
  return out;
}

/** Friendly names for the technical components shown in the active configuration. */
export function modelLabel(provider: string, version: string): { name: string; detail: string } {
  if (provider === "fake") return { name: "Simulado (reglas y plantillas)", detail: "Sin IA externa: gratis y predecible, para pruebas" };
  const model = version.split("/")[0];
  const names: Record<string, string> = { "deepseek-flash": "DeepSeek Flash", "deepseek-v4-flash": "DeepSeek Flash", "deepseek-v4-pro": "DeepSeek Pro" };
  return { name: names[model] ?? model, detail: "Solo entiende el mensaje y redacta; no decide ni ejecuta acciones" };
}

/** Friendly name for the ml-service classifier model (keyword stub, trained model or unavailable). */
export function classifierLabel(model: string): { name: string; detail: string } {
  if (model === "unavailable") return { name: "No disponible", detail: "El servicio de clasificación no responde" };
  if (model.startsWith("keyword-stub")) return { name: "Palabras clave (provisional)", detail: "Se reemplazará por el modelo entrenado" };
  return { name: model, detail: "Modelo entrenado que identifica el tipo de caso" };
}

/** Explains a team_generated policy origin; any other origin is shown as is. */
export function originLabel(origin: string): string {
  return origin.startsWith("team_generated")
    ? "Política de ejemplo creada por el equipo para el hackathon; no es la política de un banco real."
    : origin;
}
