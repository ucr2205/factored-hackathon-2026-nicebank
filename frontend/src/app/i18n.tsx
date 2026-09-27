import { createContext, useContext, useState, type ReactNode } from "react";

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
    navConsole: "Consola",
    navSupervisor: "Supervisión",
    myCards: "Mis tarjetas",
    hello: "Hola",
    cardActive: "Activa",
    cardBlocked: "Bloqueada",
    noCards: "No tienes tarjetas activas.",
    recentMovements: "Movimientos recientes",
    tapToDispute: "Toca uno para disputarlo",
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
    navConsole: "Console",
    navSupervisor: "Supervisão",
    myCards: "Meus cartões",
    hello: "Olá",
    cardActive: "Ativo",
    cardBlocked: "Bloqueado",
    noCards: "Você não tem cartões ativos.",
    recentMovements: "Movimentações recentes",
    tapToDispute: "Toque em uma para contestar",
    redirecting: "Redirecionando para o login seguro…",
  },
} as const;

type Strings = (typeof STRINGS)["es"];

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: Strings } | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (navigator.language.startsWith("pt") ? "pt" : "es"));
  return <LangContext value={{ lang, setLang, t: STRINGS[lang] as Strings }}>{children}</LangContext>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}

const LOCALES: Record<Lang, string> = { es: "es-MX", pt: "pt-BR" };

// Intl throws on a non-ISO currency or an unparseable date; one bad dataset row must not blank the page.
export function formatMoney(amount: number, currency: string, lang: Lang) {
  try {
    return new Intl.NumberFormat(LOCALES[lang], { style: "currency", currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

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
