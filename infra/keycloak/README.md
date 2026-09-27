# Keycloak realm (`latam-bank`)

Imported on startup (`start-dev --import-realm`). **Test environment only**: all users, passwords and the
`eval-harness` client secret in `latam-bank-realm.json` are local test values, not real credentials.

- `web`: public client, Authorization Code + PKCE (S256), redirect `http://localhost:5173/*`.
- `eval-harness`: confidential client with direct access grants, used only by the offline evaluation harness.
  Remove it in any real deployment.
- Roles: `customer`, `agent`, `supervisor`. The `customer_id` user attribute is mapped into access tokens;
  the backend takes the customer identity from this claim only.
- Test users `cliente01`..`cliente20` (customers; `customer_id` set by `etl/seed_demo.py` from the demo subset),
  `agente01`, `agente02` (agents) and `supervisor01`. Password pattern: `Test-Only-<username>`.
- Step-up: browser flow `browser-step-up` with levels of authentication (LoA 1 = password, LoA 2 = password +
  TOTP, max age 5 min). The web app requests `acr_values=2` before `block_card`; the backend refuses the action
  when the token's `acr` is below 2.
- Demo customers carry a test-only TOTP seed (`nicebank-demo-otp-<username>`, raw secret, SHA1, 6 digits, 30 s)
  so the step-up demo works without enrolling a phone. `scripts/smoke_chat.py` shows how to compute a code.
- Login theme `nicebank` (`themes/nicebank/login`): branded layout for every Keycloak page (login, TOTP, logout,
  password recovery). Email theme `nicebank` (`themes/nicebank/email`) for the password-reset email.
- Password recovery (`resetCredentialsFlow = reset-credentials-verified`): username -> single-use email link
  (10 min) -> **verify** the existing TOTP when the user has one -> new password (policy: 8+ chars, upper, lower,
  digit, not the username). Keycloak's default reset flow *resets* OTP instead, which would let someone with access
  to the mailbox enroll their own authenticator; the custom flow avoids that.
- Emails go to Mailpit (http://localhost:8025) in local development; nothing is sent to real inboxes.
