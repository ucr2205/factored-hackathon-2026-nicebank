// Staff-facing labels for the agent console and supervisor view, in the UI language (es/pt).
import type { Lang } from "../../app/i18n";

type Labels = Record<Lang, Record<string, string>>;

export const REASONS: Labels = {
  es: {
    possible_fraud_high_amount: "Posible fraude · monto alto",
    card_lost_or_stolen: "Tarjeta perdida o robada",
    outside_automatic_window: "Fuera del plazo automático",
    could_not_identify_transaction: "No se identificó el movimiento",
    technical_failure: "Falla técnica",
    action_not_verified: "Acción no verificada",
    high_amount_duplicate: "Duplicado de monto alto",
    high_amount_dispute: "Disputa de monto alto",
    baseline_human_review: "Revisión humana (baseline)",
    declined_unrecognized_attempt: "Intento rechazado no reconocido",
  },
  pt: {
    possible_fraud_high_amount: "Possível fraude · valor alto",
    card_lost_or_stolen: "Cartão perdido ou roubado",
    outside_automatic_window: "Fora do prazo automático",
    could_not_identify_transaction: "Movimentação não identificada",
    technical_failure: "Falha técnica",
    action_not_verified: "Ação não verificada",
    high_amount_duplicate: "Duplicidade de valor alto",
    high_amount_dispute: "Contestação de valor alto",
    baseline_human_review: "Revisão humana (baseline)",
    declined_unrecognized_attempt: "Tentativa recusada não reconhecida",
  },
};

export const DISPUTE_TYPES: Labels = {
  es: {
    unrecognized_charge: "Cargo no reconocido",
    duplicate_charge: "Cargo duplicado",
    wrong_amount: "Monto incorrecto",
    not_received: "Compra no recibida",
    atm_cash_not_dispensed: "Cajero no entregó efectivo",
    card_lost_stolen: "Tarjeta perdida o robada",
    other_in_scope: "Otro problema con la tarjeta",
    out_of_scope: "Fuera de alcance",
  },
  pt: {
    unrecognized_charge: "Cobrança não reconhecida",
    duplicate_charge: "Cobrança duplicada",
    wrong_amount: "Valor incorreto",
    not_received: "Compra não recebida",
    atm_cash_not_dispensed: "Caixa eletrônico não liberou o dinheiro",
    card_lost_stolen: "Cartão perdido ou roubado",
    other_in_scope: "Outro problema com o cartão",
    out_of_scope: "Fora do escopo",
  },
};

export const STEPS: Labels = {
  es: {
    understand: "Entender",
    extract: "Extraer datos",
    find_transactions: "Buscar movimientos",
    policy: "Evaluar política",
    propose: "Proponer acción",
    confirm: "Confirmación del cliente",
    act: "Ejecutar",
    verify: "Verificar",
    handoff: "Pasar a humano",
    identity: "Identidad del cliente",
    notify: "Correo al cliente",
    respond: "Responder",
  },
  pt: {
    understand: "Entender",
    extract: "Extrair dados",
    find_transactions: "Buscar movimentações",
    policy: "Avaliar política",
    propose: "Propor ação",
    confirm: "Confirmação do cliente",
    act: "Executar",
    verify: "Verificar",
    handoff: "Transferir para humano",
    identity: "Identidade do cliente",
    notify: "E-mail ao cliente",
    respond: "Responder",
  },
};

export const LANGS: Labels = {
  es: { es: "Español", pt: "Portugués" },
  pt: { es: "Espanhol", pt: "Português" },
};

// Queues are "<team>_<lang>" (e.g. fraud_es): shown as "Fraudes · español".
const QUEUE_TEAMS: Labels = { es: { disputes: "Disputas", fraud: "Fraudes" }, pt: { disputes: "Contestações", fraud: "Fraudes" } };
const QUEUE_LANGS: Labels = { es: { es: "español", pt: "portugués" }, pt: { es: "espanhol", pt: "português" } };
/** Readable queue name; unknown team or language parts are shown as they come. */
export const queueLabel = (q: string, lang: Lang) => {
  const [team, queueLang] = q.split("_");
  return [QUEUE_TEAMS[lang][team] ?? team, QUEUE_LANGS[lang][queueLang] ?? queueLang].filter(Boolean).join(" · ");
};

export const ACTION_NAMES: Labels = {
  es: { open_dispute_case: "Disputa abierta", block_card: "Tarjeta bloqueada" },
  pt: { open_dispute_case: "Contestação aberta", block_card: "Cartão bloqueado" },
};

export const ACTION_STATUS: Labels = {
  es: { verified: "verificada", failed: "falló", pending: "pendiente" },
  pt: { verified: "verificada", failed: "falhou", pending: "pendente" },
};

// Where each verified fact was read from.
export const SOURCES: Labels = {
  es: {
    transactions: "movimientos de la tarjeta",
    exchange_rates: "tasas de cambio del día",
    card_blocks: "registro de bloqueos",
    dispute_cases: "registro de disputas",
    products: "productos del cliente",
  },
  pt: {
    transactions: "movimentações do cartão",
    exchange_rates: "taxas de câmbio do dia",
    card_blocks: "registro de bloqueios",
    dispute_cases: "registro de contestações",
    products: "produtos do cliente",
  },
};
