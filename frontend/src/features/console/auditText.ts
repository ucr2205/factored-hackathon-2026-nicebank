// Turns the backend's technical audit summaries (English, stable formats written by the orchestrator) into
// plain Spanish or Portuguese for agents. The raw summary stays available behind the technical-detail switch.
import type { AuditEvent } from "../../api/types";
import { LOCALES, type Lang } from "../../app/i18n";
import { DISPUTE_TYPES, queueLabel, REASONS } from "./labels";

const ACTIONS: Record<Lang, Record<string, string>> = {
  es: { open_dispute_case: "abrir la disputa", block_card: "bloquear la tarjeta" },
  pt: { open_dispute_case: "abrir a contestação", block_card: "bloquear o cartão" },
};

const EMAILS: Record<Lang, Record<string, string>> = {
  es: { case_opened: "disputa abierta", card_blocked: "tarjeta bloqueada", handoff_created: "caso con especialista" },
  pt: { case_opened: "contestação aberta", card_blocked: "cartão bloqueado", handoff_created: "caso com especialista" },
};

/** Short, readable reference for long ids (same as the customer sees in emails). */
export const shortRef = (id: string) => (id.length > 12 ? id.slice(0, 8).toUpperCase() : id);

const TXN_STATUS: Record<Lang, Record<string, string>> = {
  es: { Approved: "aprobado", Pending: "pendiente", Declined: "rechazado", Rejected: "rechazado", Reversed: "revertido" },
  pt: { Approved: "aprovado", Pending: "pendente", Declined: "recusado", Rejected: "recusado", Reversed: "estornado" },
};

const money = (v: string, lang: Lang) =>
  Number(v).toLocaleString(LOCALES[lang], { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const dayText = (iso: string, lang: Lang) =>
  new Intl.DateTimeFormat(LOCALES[lang], { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(iso));

type Format = (m: RegExpMatchArray, e: AuditEvent) => string;
type Rule = [RegExp, Record<Lang, Format>];

/** "Datos entendidos" line for the extract step: amount, date (or range) and whether a merchant was mentioned. */
function factsUnderstood(m: RegExpMatchArray, lang: Lang) {
  const w = lang === "pt"
    ? { amount: "valor", date: "data", between: "entre", and: "e", merchant: "estabelecimento mencionado", head: "Dados entendidos" }
    : { amount: "monto", date: "fecha", between: "entre", and: "y", merchant: "comercio mencionado", head: "Datos entendidos" };
  const parts: string[] = [];
  if (m[1]) parts.push(`${w.amount} ${money(m[1], lang)}`);
  if (m[2]) parts.push(m[2] === m[3] ? `${w.date} ${dayText(m[2], lang)}` : `${w.between} ${dayText(m[2], lang)} ${w.and} ${dayText(m[3], lang)}`);
  if (m[4]) parts.push(w.merchant);
  return `${w.head}: ${parts.join(" · ")}`;
}

const RULES: Rule[] = [
  [/^handoff (\S+) to queue (\S+) \(reason (\S+)\)$/, {
    es: (m) => `Caso ${shortRef(m[1])} enviado a la cola ${queueLabel(m[2], "es")} · motivo: ${REASONS.es[m[3]] ?? m[3]}`,
    pt: (m) => `Caso ${shortRef(m[1])} enviado para a fila ${queueLabel(m[2], "pt")} · motivo: ${REASONS.pt[m[3]] ?? m[3]}`,
  }],
  [/^turn completed$/, { es: () => "Respuesta enviada al cliente", pt: () => "Resposta enviada ao cliente" }],
  [/^customer identity revealed to (\S+) for handoff (\S+)$/, {
    es: (m) => `${m[1]} consultó la identidad del cliente del caso ${shortRef(m[2])}`,
    pt: (m) => `${m[1]} consultou a identidade do cliente do caso ${shortRef(m[2])}`,
  }],
  [/^handoff closed by (\S+)$/, {
    es: (m, e) => `${m[1]} cerró el caso: ${e.result === "accepted" ? "resuelto a favor del cliente" : "no procede"}`,
    pt: (m, e) => `${m[1]} encerrou o caso: ${e.result === "accepted" ? "resolvido a favor do cliente" : "não procede"}`,
  }],
  [/^label=(\w+) confidence=([\d.]+) abstain=(\w+) model=(\S+)$/, {
    es: (m) =>
      `Clasificó el mensaje como «${DISPUTE_TYPES.es[m[1]] ?? m[1]}» con ${Math.round(Number(m[2]) * 100)}% de confianza${m[3] === "true" ? " (sin certeza suficiente: pregunta al cliente)" : ""}`,
    pt: (m) =>
      `Classificou a mensagem como «${DISPUTE_TYPES.pt[m[1]] ?? m[1]}» com ${Math.round(Number(m[2]) * 100)}% de confiança${m[3] === "true" ? " (sem certeza suficiente: pergunta ao cliente)" : ""}`,
  }],
  [/^classification failed/, {
    es: () => "El clasificador no respondió tras los reintentos",
    pt: () => "O classificador não respondeu após as novas tentativas",
  }],
  [/^instruction-override or forbidden-action pattern/, {
    es: () => "Mensaje bloqueado: intentó cambiar las instrucciones del asistente o pedir una acción prohibida",
    pt: () => "Mensagem bloqueada: tentou mudar as instruções do assistente ou pedir uma ação proibida",
  }],
  [/^customer names unavailable/, {
    es: () => "No se pudieron descifrar los nombres; el enmascarado usó solo patrones",
    pt: () => "Não foi possível descriptografar os nomes; o mascaramento usou apenas padrões",
  }],
  [/^customer picked candidate (\d+) of (\d+)$/, {
    es: (m) => `El cliente eligió el movimiento ${m[1]} de ${m[2]}`,
    pt: (m) => `O cliente escolheu a movimentação ${m[1]} de ${m[2]}`,
  }],
  [/^no facts extracted$/, {
    es: () => "No se identificó monto, fecha ni comercio en el mensaje",
    pt: () => "Nenhum valor, data ou estabelecimento identificado na mensagem",
  }],
  [/^(?:amount=([\d.]+))?\s*(?:date=(\S+)\.\.(\S+))?\s*(merchant_hint=yes)?$/, {
    es: (m) => factsUnderstood(m, "es"),
    pt: (m) => factsUnderstood(m, "pt"),
  }],
  [/^(\d+) candidate\(s\) for type=(\w*)$/, {
    es: (m) => (Number(m[1]) === 0 ? "Ningún movimiento de sus tarjetas coincide" : `${m[1]} movimiento(s) de sus tarjetas coinciden`),
    pt: (m) => (Number(m[1]) === 0 ? "Nenhuma movimentação dos cartões do cliente coincide" : `${m[1]} movimentação(ões) dos cartões do cliente coincidem`),
  }],
  [/^type=card_lost_stolen$/, {
    es: () => "Tarjeta perdida o robada: siempre se proponen bloqueo y especialista",
    pt: () => "Cartão perdido ou roubado: sempre se propõem bloqueio e especialista",
  }],
  [/^type=(\w+) txn=(\S+) age_days=(\d+) status=(\S+) amount_usd=([\d.]+) fx=(.*)$/, {
    es: (m) =>
      `${DISPUTE_TYPES.es[m[1]] ?? m[1]} · movimiento de hace ${m[3]} días · ${money(m[5], "es")} USD (${m[6]}) · estado ${TXN_STATUS.es[m[4]] ?? m[4]}`,
    pt: (m) =>
      `${DISPUTE_TYPES.pt[m[1]] ?? m[1]} · movimentação de ${m[3]} dias atrás · ${money(m[5], "pt")} USD (${m[6]}) · status ${TXN_STATUS.pt[m[4]] ?? m[4]}`,
  }],
  [/^transaction already has open case (\S+)$/, {
    es: (m) => `El movimiento ya tiene la disputa ${m[1]} abierta; no se duplicó`,
    pt: (m) => `A movimentação já tem a contestação ${m[1]} aberta; não foi duplicada`,
  }],
  [/^pending action (\S+) awaiting customer confirmation$/, {
    es: (m) => `Se propuso ${ACTIONS.es[m[1]] ?? m[1]}; espera la confirmación del cliente`,
    pt: (m) => `Foi proposto ${ACTIONS.pt[m[1]] ?? m[1]}; aguarda a confirmação do cliente`,
  }],
  [/^customer declined the proposed action$/, {
    es: (_m, e) => `El cliente rechazó ${ACTIONS.es[e.tool ?? ""] ?? "la acción"}`,
    pt: (_m, e) => `O cliente recusou ${ACTIONS.pt[e.tool ?? ""] ?? "a ação"}`,
  }],
  [/^customer confirmed the proposed action$/, {
    es: (_m, e) => `El cliente confirmó ${ACTIONS.es[e.tool ?? ""] ?? "la acción"}`,
    pt: (_m, e) => `O cliente confirmou ${ACTIONS.pt[e.tool ?? ""] ?? "a ação"}`,
  }],
  [/^executed (\S+) -> (\S+)$/, {
    es: (m) => `Se ejecutó: ${ACTIONS.es[m[1]] ?? m[1]} (${m[2]})`,
    pt: (m) => `Executado: ${ACTIONS.pt[m[1]] ?? m[1]} (${m[2]})`,
  }],
  [/^read back (\S+) and confirmed the new state$/, {
    es: (m) => `Se releyó ${m[1]} en la base de datos y se confirmó el cambio`,
    pt: (m) => `${m[1]} foi relido no banco de dados e a mudança foi confirmada`,
  }],
  [/^action could not be verified/, {
    es: () => "No se pudo confirmar la acción; el caso pasó a un especialista",
    pt: () => "Não foi possível confirmar a ação; o caso passou para um especialista",
  }],
  [/^email (\w+) queued$/, {
    es: (m) => `Correo «${EMAILS.es[m[1]] ?? m[1]}» en cola de envío`,
    pt: (m) => `E-mail «${EMAILS.pt[m[1]] ?? m[1]}» na fila de envio`,
  }],
  [/^could not queue (\w+)/, {
    es: (m) => `No se pudo preparar el correo «${EMAILS.es[m[1]] ?? m[1]}»`,
    pt: (m) => `Não foi possível preparar o e-mail «${EMAILS.pt[m[1]] ?? m[1]}»`,
  }],
  [/^email (\w+) #\d+, attempt (\d+)$/, {
    es: (m, e) =>
      `Correo «${EMAILS.es[m[1]] ?? m[1]}» ${e.result === "sent" ? "enviado" : e.result === "failed" ? "no se pudo enviar" : "se reintentará"} (intento ${m[2]})`,
    pt: (m, e) =>
      `E-mail «${EMAILS.pt[m[1]] ?? m[1]}» ${e.result === "sent" ? "enviado" : e.result === "failed" ? "não pôde ser enviado" : "será reenviado"} (tentativa ${m[2]})`,
  }],
];

/** Readable description of an audit event in the UI language; falls back to the raw summary for unknown formats. */
export function describeAudit(e: AuditEvent, lang: Lang): string {
  for (const [re, fmt] of RULES) {
    const m = e.summary.match(re);
    if (m && m[0] !== "") return fmt[lang](m, e);
  }
  return e.summary;
}

const RESULTS: Record<Lang, Record<string, string>> = {
  es: {
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
  },
  pt: {
    verified: "Verificado",
    executed: "Executado",
    not_verified: "Não verificado",
    confirmed: "Confirmado",
    cancelled: "Recusado",
    pending: "Pendente",
    selected: "Escolhido",
    blocked: "Bloqueado",
    error: "Erro",
    degraded: "Degradado",
    existing_case: "Caso existente",
    revealed: "Consultada",
    queued: "Na fila",
    sent: "Enviado",
    retry: "Nova tentativa",
    failed: "Falhou",
    resolve: "Resolvido",
    clarify: "Pede esclarecimento",
    abstain: "Fora do escopo",
    escalate: "Escalonado",
    confirm: "Pede confirmação",
    auto: "Automático",
  },
};

/** Readable names for policy rule ids; the id itself is kept in the tooltip for auditors. */
export const RULE_NAMES: Record<Lang, Record<string, string>> = {
  es: {
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
    "DISP-AUTO-03": "Monto incorrecto automático",
    "DISP-AUTO-04": "No recibido automático",
    "DISP-AUTO-05": "Cajero automático",
    "EXPLAIN-REVERSED": "Explicado: ya revertido",
    "EXPLAIN-DECLINED": "Explicado: compra rechazada",
    "EXPLAIN-DECLINED-FRAUD": "Intento rechazado: bloqueo",
    "EXPLAIN-PENDING": "Explicado: aún pendiente",
  },
  pt: {
    "BASELINE-01": "Baseline: tudo para humano",
    "SCOPE-01": "Fora do escopo",
    "SEC-INJ-01": "Tentativa de manipulação",
    "CLARIFY-TYPE": "Tipo de caso não claro",
    "CLARIFY-NOTFOUND": "Movimentação não encontrada",
    "CLARIFY-MULTI": "Várias movimentações possíveis",
    "ESC-CLARIFY-LIMIT": "Limite de esclarecimentos",
    "ESC-TECH-01": "Falha técnica",
    "DISP-DUPCASE-01": "Já tem contestação aberta",
    "DISP-AUTO-01": "Contestação automática",
    "DISP-AUTO-02": "Duplicidade automática",
    "DISP-ELIG-01": "Fora do prazo ou status",
    "DISP-ESC-01": "Valor alto: possível fraude",
    "DISP-ESC-02": "Cartão perdido ou roubado",
    "DISP-ESC-04": "Duplicidade de valor alto",
    "DISP-ESC-05": "Valor alto",
    "DISP-ESC-06": "Valor alto",
    "DISP-ESC-07": "Valor alto",
    "DISP-AUTO-03": "Valor incorreto automático",
    "DISP-AUTO-04": "Não recebido automático",
    "DISP-AUTO-05": "Caixa eletrônico automático",
    "EXPLAIN-REVERSED": "Explicado: já estornado",
    "EXPLAIN-DECLINED": "Explicado: compra recusada",
    "EXPLAIN-DECLINED-FRAUD": "Tentativa recusada: bloqueio",
    "EXPLAIN-PENDING": "Explicado: ainda pendente",
  },
};

/** Numeric results (candidate counts) are already in the description. */
export const resultLabel = (r: string | null, lang: Lang) =>
  r && !/^\d+$/.test(r) ? RESULTS[lang][r] ?? DISPUTE_TYPES[lang][r] ?? r : null;
