import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";
import { stepUpNavigator } from "./modalNavigator";

// Authorization Code + PKCE against Keycloak. Tokens live in memory only (never localStorage).
// The OIDC state for the redirect round-trip uses sessionStorage (default), which holds no tokens.
// The "popup" flow is used only for step-up and runs in an in-page dialog (ModalNavigator), not a browser window.
export const userManager = new UserManager(
  {
    authority: import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/realms/latam-bank",
    client_id: import.meta.env.VITE_OIDC_CLIENT_ID ?? "web",
    redirect_uri: `${window.location.origin}/`,
    popup_redirect_uri: `${window.location.origin}/stepup-callback.html`,
    post_logout_redirect_uri: `${window.location.origin}/`,
    response_type: "code",
    scope: "openid",
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
  },
  undefined,
  stepUpNavigator,
);

export type Claims = {
  preferred_username?: string;
  customer_ref?: string; // opaque pseudonym; the bank's customer_id never reaches the browser
  acr?: string;
  realm_access?: { roles?: string[] };
};

// Display only: the backend verifies the token. A malformed token yields no claims instead of crashing the app.
export function decodeClaims(accessToken: string): Claims {
  try {
    const payload = (accessToken.split(".")[1] ?? "").replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(payload.padEnd(Math.ceil(payload.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)) as Claims;
  } catch {
    return {};
  }
}
