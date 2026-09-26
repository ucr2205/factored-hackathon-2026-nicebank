import { useEffect, useState } from "react";
import type { User } from "oidc-client-ts";
import { decodeClaims, userManager } from "./auth";
import "./App.css";

type Lang = "es" | "pt";

const TEXT: Record<Lang, Record<string, string>> = {
  es: {
    title: "Atención de disputas",
    login: "Iniciar sesión",
    logout: "Cerrar sesión",
    placeholder: "Escribe tu mensaje…",
    send: "Enviar",
    notReady: "El chat se conecta al backend en el día 2.",
  },
  pt: {
    title: "Atendimento de contestações",
    login: "Entrar",
    logout: "Sair",
    placeholder: "Escreva sua mensagem…",
    send: "Enviar",
    notReady: "O chat se conecta ao backend no dia 2.",
  },
};

// The redirect callback must run once even though StrictMode mounts effects twice in development.
let callbackOnce: Promise<User> | null = null;

// Phase 0 shell: PKCE login, session claims and an unconnected chat box.
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [lang, setLang] = useState<Lang>("es");
  const [error, setError] = useState<string | null>(null);
  const t = TEXT[lang];

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("code") && params.has("state")) {
      callbackOnce ??= userManager.signinRedirectCallback();
      callbackOnce
        .then((u) => {
          setUser(u);
          window.history.replaceState({}, "", "/");
        })
        .catch((e: Error) => setError(e.message));
    }
  }, []);

  const claims = user ? decodeClaims(user.access_token) : null;

  return (
    <main className="shell">
      <header className="bar">
        <h1>{t.title}</h1>
        <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label="Language">
          <option value="es">Español</option>
          <option value="pt">Português</option>
        </select>
        {user ? (
          <button onClick={() => userManager.signoutRedirect()}>{t.logout}</button>
        ) : (
          <button onClick={() => userManager.signinRedirect()}>{t.login}</button>
        )}
      </header>

      {error && <p className="error">{error}</p>}

      {claims && (
        <section className="session">
          <code>
            user={claims.preferred_username} · customer_id={claims.customer_id} · acr={claims.acr} · roles=
            {claims.realm_access?.roles?.join(",")}
          </code>
        </section>
      )}

      <section className="chat">
        <p className="hint">{t.notReady}</p>
        <form onSubmit={(e) => e.preventDefault()}>
          <input placeholder={t.placeholder} disabled={!user} />
          <button type="submit" disabled={!user}>
            {t.send}
          </button>
        </form>
      </section>
    </main>
  );
}
