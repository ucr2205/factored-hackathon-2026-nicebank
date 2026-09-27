// Staff-facing labels (agents work in Spanish).
export const REASONS: Record<string, string> = {
  possible_fraud_high_amount: "Posible fraude · monto alto",
  card_lost_or_stolen: "Tarjeta perdida o robada",
  outside_automatic_window: "Fuera del plazo automático",
  could_not_identify_transaction: "No se identificó el movimiento",
  technical_failure: "Falla técnica",
  action_not_verified: "Acción no verificada",
  high_amount_duplicate: "Duplicado de monto alto",
  high_amount_dispute: "Disputa de monto alto",
  baseline_human_review: "Revisión humana (baseline)",
};

export const DISPUTE_TYPES: Record<string, string> = {
  unrecognized_charge: "Cargo no reconocido",
  duplicate_charge: "Cargo duplicado",
  wrong_amount: "Monto incorrecto",
  not_received: "Compra no recibida",
  atm_cash_not_dispensed: "Cajero no entregó efectivo",
  card_lost_stolen: "Tarjeta perdida o robada",
};

export const STEPS: Record<string, string> = {
  understand: "Entender",
  extract: "Extraer datos",
  find_transactions: "Buscar movimientos",
  policy: "Evaluar política",
  propose: "Proponer acción",
  confirm: "Confirmación del cliente",
  act: "Ejecutar",
  verify: "Verificar",
  handoff: "Pasar a humano",
  identity: "Ver identidad del cliente",
  respond: "Responder",
};

export const LANGS: Record<string, string> = { es: "Español", pt: "Portugués" };

export const PRIORITY_COLOR = { high: "error", medium: "warning", low: "default" } as const;

export const PRIORITY_LABEL = { high: "alta", medium: "media", low: "baja" } as const;
