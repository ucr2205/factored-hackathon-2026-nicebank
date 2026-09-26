# frontend

React + Vite + TypeScript app: customer login (Keycloak, Authorization Code + PKCE), chat, and the internal
agent console. Tokens are kept in memory only.

```bash
npm install
npm run dev      # http://localhost:5173 (Keycloak must be running: docker compose up -d keycloak)
npm run build
```

Config via env: `VITE_OIDC_AUTHORITY` (default `http://localhost:8080/realms/latam-bank`), `VITE_OIDC_CLIENT_ID` (default `web`).
