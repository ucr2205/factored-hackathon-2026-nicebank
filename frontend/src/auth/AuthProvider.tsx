import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User } from "oidc-client-ts";
import { useLang } from "../app/i18n";
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
  stepUp: (resume: ResumeState) => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

// The redirect callback must run once even though StrictMode mounts effects twice in development.
let callbackOnce: Promise<User> | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [resume, setResume] = useState<ResumeState | null>(null);
  const { lang } = useLang();
  const uiLocales = lang === "pt" ? "pt-BR" : "es";

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
        const state = u.state as { resume?: ResumeState; returnTo?: string } | undefined;
        if (state?.resume) setResume(state.resume);
        window.history.replaceState({}, "", state?.returnTo ?? "/");
      })
      .catch(() => window.history.replaceState({}, "", "/"))
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(() => userManager.signinRedirect({ ui_locales: uiLocales }), [uiLocales]);
  const logout = useCallback(() => userManager.signoutRedirect({ extraQueryParams: { ui_locales: uiLocales } }), [uiLocales]);
  // Step-up: ask Keycloak for level 2 (password + TOTP), then come back to the chat and resume.
  const stepUp = useCallback(
    (r: ResumeState) =>
      userManager.signinRedirect({ acr_values: "2", ui_locales: uiLocales, state: { resume: r, returnTo: "/chat" } }),
    [uiLocales],
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

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
