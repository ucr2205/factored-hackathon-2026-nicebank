import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";

// Authorization Code + PKCE against Keycloak. Tokens live in memory only (never localStorage).
export const userManager = new UserManager({
  authority: import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/realms/latam-bank",
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID ?? "web",
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: "openid",
  userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
});

export type Claims = {
  preferred_username?: string;
  customer_id?: string;
  acr?: string;
  realm_access?: { roles?: string[] };
};

export function decodeClaims(accessToken: string): Claims {
  const payload = accessToken.split(".")[1] ?? "";
  const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json) as Claims;
}
