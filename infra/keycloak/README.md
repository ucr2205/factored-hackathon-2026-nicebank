# Keycloak realm (`latam-bank`)

Imported on startup (`start-dev --import-realm`). **Test environment only**: all users, passwords and the
`eval-harness` client secret in `latam-bank-realm.json` are local test values, not real credentials.

- `web`: public client, Authorization Code + PKCE (S256), redirect `http://localhost:5173/*`.
- `eval-harness`: confidential client with direct access grants, used only by the offline evaluation harness.
  Remove it in any real deployment.
- Roles: `customer`, `agent`, `supervisor`. The `customer_id` user attribute is mapped into access tokens;
  the backend takes the customer identity from this claim only.
- Test users `cliente01`, `cliente02` (customers, placeholder `customer_id` until demo customers are chosen
  from the dataset) and `agente01` (agent).
- TODO (D2): step-up flow (LoA 2 = password + TOTP) for sensitive actions such as `block_card`.
