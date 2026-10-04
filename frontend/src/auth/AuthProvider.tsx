// OIDC session for the whole app (Keycloak, Authorization Code + PKCE): login/logout redirects, the redirect
// callback, roles from the access token and the TOTP step-up (acr 2). Talks only to Keycloak, never to the API.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User } from "oidc-client-ts";
import { langFromLocale, useLang } from "../app/i18n";
import { STEP_UP_CANCELLED } from "./modalNavigator";
import { decodeClaims, userManager, type Claims } from "./oidc";

export type Role = "customer" | "agent" | "supervisor";

/** Data carried through a step-up redirect so the chat can resume the confirmed action. */
export type ResumeState = { sessionId: string; actionId: string };

type AuthValue = {
  user: User | null;
  claims: Claims | null;
  roles: Role[];
  ready: boolean;
  resume: ResumeState | null;
  clearResume: () => void;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  /** Resolves with the level-2 user when the in-page step-up succeeds, or null if it was cancelled or the page
   *  is leaving for the full-page fallback. */
  stepUp: (resume: ResumeState) => Promise<User | null>;
};

const AuthContext = createContext<AuthValue | null>(null);

// The redirect callback must run once even though StrictMode mounts effects twice in development.
let callbackOnce: Promise<User> | null = null;

/** Provides the signed-in user, decoded claims, roles and the login, logout and step-up actions. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [resume, setResume] = useState<ResumeState | null>(null);
  const { lang, setLang } = useLang();
  const uiLocales = lang === "pt" ? "pt-BR" : "es";
  // ui_locales alone loses to the language a known user saved earlier (Keycloak's profile attribute), so the OTP
  // and reset pages could show the other language; kc_locale wins over it and updates that attribute.
  const localeParams = useMemo(() => ({ ui_locales: uiLocales, extraQueryParams: { kc_locale: uiLocales } }), [uiLocales]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!(params.has("code") && params.has("state"))) {
      setReady(true);
      return;
    }
    callbackOnce ??= userManager.signinRedirectCallback();
    callbackOnce
      .then((u) => {
        setUser(u);
        // The customer may have switched language on Keycloak's own page: follow it (ID token "locale" claim).
        const chosen = langFromLocale((u.profile as { locale?: string }).locale);
        if (chosen) setLang(chosen);
        const state = u.state as { resume?: ResumeState; returnTo?: string } | undefined;
        if (state?.resume) setResume(state.resume);
        window.history.replaceState({}, "", state?.returnTo ?? "/");
      })
      .catch(() => window.history.replaceState({}, "", "/"))
      .finally(() => setReady(true));
  }, [setLang]);

  const login = useCallback(() => userManager.signinRedirect(localeParams), [localeParams]);
  const logout = useCallback(() => userManager.signoutRedirect({ extraQueryParams: { ui_locales: uiLocales, kc_locale: uiLocales } }), [uiLocales]);
  // Step-up: ask Keycloak for level 2 (password + TOTP) in a dialog over the current page. If the dialog cannot
  // be used (or the customer asks for it), fall back to the full-page redirect, which resumes the chat on return.
  const stepUp = useCallback(
    async (r: ResumeState) => {
      try {
        const upgraded = await userManager.signinPopup({ acr_values: "2", ...localeParams });
        setUser(upgraded);
        return upgraded;
      } catch (e) {
        if (e instanceof Error && e.message === STEP_UP_CANCELLED) return null;
        await userManager.signinRedirect({ acr_values: "2", ...localeParams, state: { resume: r, returnTo: "/chat" } });
        return null;
      }
    },
    [localeParams],
  );
  const clearResume = useCallback(() => setResume(null), []);

  const value = useMemo<AuthValue>(() => {
    const claims = user ? decodeClaims(user.access_token) : null;
    const roles = (claims?.realm_access?.roles ?? []).filter((r): r is Role =>
      ["customer", "agent", "supervisor"].includes(r),
    );
    return { user, claims, roles, ready, resume, clearResume, login, logout, stepUp };
  }, [user, ready, resume, clearResume, login, logout, stepUp]);

  return <AuthContext value={value}>{children}</AuthContext>;
}

/** Auth context accessor; throws outside AuthProvider. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
