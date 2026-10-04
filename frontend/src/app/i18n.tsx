// UI language (es/pt: the last choice, kept in localStorage, else the browser locale; switchable in the navbar),
// every customer-facing string and locale-safe money/date formatters. Staff screens keep their own es/pt text next to each component.
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type Lang = "es" | "pt";

const STRINGS = {
  es: {
    brandTagline: "Atención de disputas",
    login: "Iniciar sesión",
    logout: "Cerrar sesión",
    chatTitle: "Asistente de disputas",
    chatPlaceholder: "Escribe tu mensaje…",
    send: "Enviar",
    newChat: "Nueva conversación",
    welcome: "Hola. Soy el asistente de disputas de NiceBank. ¿Qué cargo quieres revisar? Puedes decirme la fecha, el monto o el comercio.",
    thinking: "Revisando…",
    pickCandidate: "Elegir",
    confirm: "Confirmar",
    cancel: "No, gracias",
    stepUpNote: "Te pediremos un código de verificación de tu app autenticadora.",
    stepUpTitle: "Verificación de seguridad",
    stepUpHint: "Escribe el código de 6 dígitos de tu app autenticadora. Tu conversación sigue aquí.",
    stepUpCancel: "Cancelar",
    stepUpFullPage: "¿No carga? Ábrelo en pantalla completa",
    verified: "Verificado",
    caseNumber: "Caso",
    handoffNote: "Un especialista ya tiene tu caso.",
    sessionExpiredTitle: "Tu sesión expiró",
    sessionExpiredBody: "Por seguridad cerramos la conversación después de 15 minutos sin actividad. Puedes empezar una nueva.",
    startAgain: "Empezar de nuevo",
    errorGeneric: "Tuvimos un problema temporal. Intenta de nuevo en unos segundos.",
    card: "Tarjeta",
    suggestions: ["No reconozco un cobro de hoy", "Me cobraron dos veces", "Me robaron la tarjeta"],
    navChat: "Chat",
    navConsole: "Casos",
    navSupervisor: "Supervisión",
    staffTagline: "Centro de atención",
    roleCustomer: "Cliente",
    roleAgent: "Agente",
    roleSupervisor: "Supervisor",
    accountMenu: "Menú de la cuenta",
    myCards: "Mis tarjetas",
    hello: "Hola",
    cardActive: "Activa",
    cardBlocked: "Bloqueada",
    cardSuspended: "Suspendida",
    cardClosed: "Cerrada",
    noCards: "No tienes tarjetas activas.",
    recentMovements: "Movimientos recientes",
    tapToDispute: "Toca uno para disputarlo",
    myDisputes: "Mis disputas",
    noDisputes: "Todavía no tienes disputas ni casos con un especialista.",
    disputeCase: "Disputa",
    disputeHandoff: "Caso con especialista",
    statusOpen: "En revisión",
    statusClaimed: "Un especialista lo está revisando",
    statusClosed: "Cerrado",
    outcomeAccepted: "Resuelto a tu favor",
    outcomeRejected: "No procedente",
    redirecting: "Redirigiendo al inicio de sesión seguro…",
  },
  pt: {
    brandTagline: "Atendimento de contestações",
    login: "Entrar",
    logout: "Sair",
    chatTitle: "Assistente de contestações",
    chatPlaceholder: "Escreva sua mensagem…",
    send: "Enviar",
    newChat: "Nova conversa",
    welcome: "Olá. Sou o assistente de contestações da NiceBank. Qual cobrança você quer revisar? Pode me dizer a data, o valor ou o estabelecimento.",
    thinking: "Verificando…",
    pickCandidate: "Escolher",
    confirm: "Confirmar",
    cancel: "Não, obrigado",
    stepUpNote: "Vamos pedir um código de verificação do seu app autenticador.",
    stepUpTitle: "Verificação de segurança",
    stepUpHint: "Digite o código de 6 dígitos do seu app autenticador. Sua conversa continua aqui.",
    stepUpCancel: "Cancelar",
    stepUpFullPage: "Não carregou? Abra em tela cheia",
    verified: "Verificado",
    caseNumber: "Caso",
    handoffNote: "Um especialista já está com seu caso.",
    sessionExpiredTitle: "Sua sessão expirou",
    sessionExpiredBody: "Por segurança encerramos a conversa após 15 minutos sem atividade. Você pode começar uma nova.",
    startAgain: "Começar de novo",
    errorGeneric: "Tivemos um problema temporário. Tente novamente em alguns segundos.",
    card: "Cartão",
    suggestions: ["Não reconheço uma cobrança de hoje", "Me cobraram duas vezes", "Roubaram meu cartão"],
    navChat: "Chat",
    navConsole: "Casos",
    navSupervisor: "Supervisão",
    staffTagline: "Central de atendimento",
    roleCustomer: "Cliente",
    roleAgent: "Agente",
    roleSupervisor: "Supervisor",
    accountMenu: "Menu da conta",
    myCards: "Meus cartões",
    hello: "Olá",
    cardActive: "Ativo",
    cardBlocked: "Bloqueado",
    cardSuspended: "Suspenso",
    cardClosed: "Encerrado",
    noCards: "Você não tem cartões ativos.",
    recentMovements: "Movimentações recentes",
    tapToDispute: "Toque em uma para contestar",
    myDisputes: "Minhas contestações",
    noDisputes: "Você ainda não tem contestações nem casos com um especialista.",
    disputeCase: "Contestação",
    disputeHandoff: "Caso com especialista",
    statusOpen: "Em análise",
    statusClaimed: "Um especialista está revisando",
    statusClosed: "Encerrado",
    outcomeAccepted: "Resolvido a seu favor",
    outcomeRejected: "Não procedente",
    redirecting: "Redirecionando para o login seguro…",
  },
} as const;

type Strings = (typeof STRINGS)["es"];

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: Strings } | null>(null);

const LANG_KEY = "nb-lang";

// The choice must survive the full-page round trips to Keycloak (login, logout, step-up fallback). Storage can be
// blocked (private mode), so every access is guarded and the app falls back to the browser locale.
function storedLang(): Lang | null {
  try {
    const v = localStorage.getItem(LANG_KEY);
    return v === "es" || v === "pt" ? v : null;
  } catch {
    return null;
  }
}

/** Language of a Keycloak locale tag ("pt-BR" → pt, "es" → es); null for anything else (e.g. "en"). */
export function langFromLocale(tag: string | undefined): Lang | null {
  if (tag?.startsWith("pt")) return "pt";
  if (tag?.startsWith("es")) return "es";
  return null;
}

/** Holds the current language: the last one chosen (here or on the Keycloak pages), else the browser locale. */
export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => storedLang() ?? (navigator.language.startsWith("pt") ? "pt" : "es"));
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      // not persisted; the choice still holds until the next full page load
    }
  }, []);
  return <LangContext value={{ lang, setLang, t: STRINGS[lang] as Strings }}>{children}</LangContext>;
}

/** Current language, its setter and the string table `t`; throws outside LangProvider. */
export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}

/** Intl locale for each UI language. */
export const LOCALES: Record<Lang, string> = { es: "es-MX", pt: "pt-BR" };

// Intl throws on a non-ISO currency or an unparseable date; one bad dataset row must not blank the page.
/** Amount in the UI locale's currency format (es-MX / pt-BR); "12.34 XYZ" when Intl rejects the currency. */
export function formatMoney(amount: number, currency: string, lang: Lang) {
  try {
    return new Intl.NumberFormat(LOCALES[lang], { style: "currency", currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

/** Medium date and short time in the UI locale; the raw ISO string when it cannot be parsed. */
export function formatDateTime(iso: string, lang: Lang) {
  try {
    return new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/** Customer-voice message that starts a dispute for a movement picked from the account panel. */
export function disputeMessage(m: { amount: number; merchant: string; date: string }, lang: Lang) {
  const amount = m.amount.toFixed(2).replace(".", ",");
  const day = `${m.date.slice(8, 10)}/${m.date.slice(5, 7)}`;
  return lang === "pt"
    ? `Não reconheço a cobrança de ${amount} em ${m.merchant} de ${day}`
    : `No reconozco el cargo de ${amount} en ${m.merchant} del ${day}`;
}
