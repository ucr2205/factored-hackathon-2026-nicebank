// Turns the backend's technical audit summaries (English, stable formats written by the orchestrator) into
// plain Spanish for agents. The raw summary stays available behind "Ver detalle técnico".
import type { AuditEvent } from "../../api/types";
import { DISPUTE_TYPES, queueLabel, REASONS } from "./labels";

const ACTIONS: Record<string, string> = {
  open_dispute_case: "abrir la disputa",
  block_card: "bloquear la tarjeta",
};

const EMAILS: Record<string, string> = {
  case_opened: "disputa abierta",
  card_blocked: "tarjeta bloqueada",
  handoff_created: "caso con especialista",
};


/** Short, readable reference for long ids (same as the customer sees in emails). */
export const shortRef = (id: string) => (id.length > 12 ? id.slice(0, 8).toUpperCase() : id);

const TXN_STATUS: Record<string, string> = { Approved: "aprobado", Pending: "pendiente", Declined: "rechazado", Rejected: "rechazado", Reversed: "revertido" };

const money = (v: string) => Number(v).toLocaleString("es", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const dayText = (iso: string) =>
  new Intl.DateTimeFormat("es", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(iso));

type Rule = [RegExp, (m: RegExpMatchArray, e: AuditEvent) => string];

const RULES: Rule[] = [
  [/^handoff (\S+) to queue (\S+) \(reason (\S+)\)$/, (m) => `Caso ${shortRef(m[1])} enviado a la cola ${queueLabel(m[2])} · motivo: ${REASONS[m[3]] ?? m[3]}`],
  [/^turn completed$/, () => "Respuesta enviada al cliente"],
  [/^customer identity revealed to (\S+) for handoff (\S+)$/, (m) => `${m[1]} consultó la identidad del cliente del caso ${shortRef(m[2])}`],
  [/^handoff closed by (\S+)$/, (m, e) => `${m[1]} cerró el caso: ${e.result === "accepted" ? "resuelto a favor del cliente" : "no procede"}`],
  [/^label=(\w+) confidence=([\d.]+) abstain=(\w+) model=(\S+)$/, (m) =>
    `Clasificó el mensaje como «${DISPUTE_TYPES[m[1]] ?? m[1]}» con ${Math.round(Number(m[2]) * 100)}% de confianza${m[3] === "true" ? " (sin certeza suficiente: pregunta al cliente)" : ""}`],
  [/^classification failed/, () => "El clasificador no respondió tras los reintentos"],
  [/^instruction-override or forbidden-action pattern/, () => "Mensaje bloqueado: intentó cambiar las instrucciones del asistente o pedir una acción prohibida"],
  [/^customer names unavailable/, () => "No se pudieron descifrar los nombres; el enmascarado usó solo patrones"],
  [/^customer picked candidate (\d+) of (\d+)$/, (m) => `El cliente eligió el movimiento ${m[1]} de ${m[2]}`],
  [/^no facts extracted$/, () => "No se identificó monto, fecha ni comercio en el mensaje"],
  [/^(?:amount=([\d.]+))?\s*(?:date=(\S+)\.\.(\S+))?\s*(merchant_hint=yes)?$/, (m) => {
    const parts: string[] = [];
    if (m[1]) parts.push(`monto ${money(m[1])}`);
    if (m[2]) parts.push(m[2] === m[3] ? `fecha ${dayText(m[2])}` : `entre ${dayText(m[2])} y ${dayText(m[3])}`);
    if (m[4]) parts.push("comercio mencionado");
    return `Datos entendidos: ${parts.join(" · ")}`;
  }],
  [/^(\d+) candidate\(s\) for type=(\w*)$/, (m) =>
    Number(m[1]) === 0 ? "Ningún movimiento de sus tarjetas coincide" : `${m[1]} movimiento(s) de sus tarjetas coinciden`],
  [/^type=card_lost_stolen$/, () => "Tarjeta perdida o robada: siempre se proponen bloqueo y especialista"],
  [/^type=(\w+) txn=(\S+) age_days=(\d+) status=(\S+) amount_usd=([\d.]+) fx=(.*)$/, (m) =>
    `${DISPUTE_TYPES[m[1]] ?? m[1]} · movimiento de hace ${m[3]} días · ${money(m[5])} USD (${m[6]}) · estado ${TXN_STATUS[m[4]] ?? m[4]}`],
  [/^transaction already has open case (\S+)$/, (m) => `El movimiento ya tiene la disputa ${m[1]} abierta; no se duplicó`],
  [/^pending action (\S+) awaiting customer confirmation$/, (m) => `Se propuso ${ACTIONS[m[1]] ?? m[1]}; espera la confirmación del cliente`],
  [/^customer declined the proposed action$/, (_m, e) => `El cliente rechazó ${ACTIONS[e.tool ?? ""] ?? "la acción"}`],
  [/^customer confirmed the proposed action$/, (_m, e) => `El cliente confirmó ${ACTIONS[e.tool ?? ""] ?? "la acción"}`],
  [/^executed (\S+) -> (\S+)$/, (m) => `Se ejecutó: ${ACTIONS[m[1]] ?? m[1]} (${m[2]})`],
  [/^read back (\S+) and confirmed the new state$/, (m) => `Se releyó ${m[1]} en la base de datos y se confirmó el cambio`],
  [/^action could not be verified/, () => "No se pudo confirmar la acción; el caso pasó a un especialista"],
  [/^email (\w+) queued$/, (m) => `Correo «${EMAILS[m[1]] ?? m[1]}» en cola de envío`],
  [/^could not queue (\w+)/, (m) => `No se pudo preparar el correo «${EMAILS[m[1]] ?? m[1]}»`],
  [/^email (\w+) #\d+, attempt (\d+)$/, (m, e) =>
    `Correo «${EMAILS[m[1]] ?? m[1]}» ${e.result === "sent" ? "enviado" : e.result === "failed" ? "no se pudo enviar" : "se reintentará"} (intento ${m[2]})`],
];

/** Readable Spanish description of an audit event; falls back to the raw summary for unknown formats. */
export function describeAudit(e: AuditEvent): string {
  for (const [re, fmt] of RULES) {
    const m = e.summary.match(re);
    if (m && m[0] !== "") return fmt(m, e);
  }
  return e.summary;
}

export const RESULTS: Record<string, string> = {
  verified: "Verificado",
  executed: "Ejecutado",
  not_verified: "No verificado",
  confirmed: "Confirmado",
  cancelled: "Rechazado",
  pending: "Pendiente",
  selected: "Elegido",
  blocked: "Bloqueado",
  error: "Error",
  degraded: "Degradado",
  existing_case: "Caso existente",
  revealed: "Consultada",
  queued: "En cola",
  sent: "Enviado",
  retry: "Reintento",
  failed: "Falló",
  resolve: "Resuelto",
  clarify: "Pide aclaración",
  abstain: "Fuera de alcance",
  escalate: "Escalado",
  confirm: "Pide confirmación",
  auto: "Automático",
};

/** Spanish names for policy rule ids; the id itself is kept in the tooltip for auditors. */
export const RULE_NAMES: Record<string, string> = {
  "BASELINE-01": "Baseline: todo a humano",
  "SCOPE-01": "Fuera de alcance",
  "SEC-INJ-01": "Intento de manipulación",
  "CLARIFY-TYPE": "Tipo de caso no claro",
  "CLARIFY-NOTFOUND": "Movimiento no encontrado",
  "CLARIFY-MULTI": "Varios movimientos posibles",
  "ESC-CLARIFY-LIMIT": "Límite de aclaraciones",
  "ESC-TECH-01": "Falla técnica",
  "DISP-DUPCASE-01": "Ya tiene disputa abierta",
  "DISP-AUTO-01": "Disputa automática",
  "DISP-AUTO-02": "Duplicado automático",
  "DISP-ELIG-01": "Fuera de plazo o estado",
  "DISP-ESC-01": "Monto alto: posible fraude",
  "DISP-ESC-02": "Tarjeta perdida o robada",
  "DISP-ESC-04": "Duplicado de monto alto",
  "DISP-ESC-05": "Monto alto",
  "DISP-ESC-06": "Monto alto",
  "DISP-ESC-07": "Monto alto",
};

/** Numeric results (candidate counts) are already in the description. */
export const resultLabel = (r: string | null) => (r && !/^\d+$/.test(r) ? RESULTS[r] ?? DISPUTE_TYPES[r] ?? r : null);
