# ADR 0005 — Customer email notifications through an outbox

Status: accepted (2026-09-27)

## Context

Customers should get an email when the assistant opens a dispute case, blocks a card or hands the case to a
specialist. The team's other products send HTML emails over SMTP (implicit TLS, port 465) with a branded
template and a sender alias. The demo dataset contains realistic-looking customer addresses (gmail, protonmail…),
so a real SMTP server must never deliver to them.

## Decision

- **Outbox.** The orchestrator inserts a `notifications` row (kind, lang, verified facts) in the same
  transaction as the action. A notification exists if and only if the action committed; nothing is sent from
  inside the request.
- **Worker.** `notify.Worker` runs in the backend, claims due rows with `claim_notifications()` (`FOR UPDATE
  SKIP LOCKED`, 5-minute lease so a crashed send is retried), decrypts the address and first name in memory
  (`customer_identity.email_ct`, ADR 0003), renders `backend/internal/notify/templates/layout.html`
  (`html/template`, auto-escaped, text/plain alternative; design follows the team's viaticos emails: dark card, NiceBank burgundy palette only (#7A1F3D line and button, logo rose #E5769A titles), inline logo, facts table with the card brand, "Important" note, call-to-action to `MAIL_APP_URL`) and sends it. `finish_notification()` records the
  result and writes an audit event without the address. Up to 4 attempts with growing back-off.
- **Transport.** `SMTP_SECURITY=ssl|starttls|none`. Default: local Mailpit (`none`). Real server:
  an SMTP server over implicit TLS on port 465 (`ssl`), login `EMAIL_USERNAME` / `EMAIL_PASSWORD` (local `.env` only), visible sender
  `NiceBank <nicebank@evon.solutions>` (`MAIL_FROM`), envelope sender = the login.
- **Guard.** With a real server the backend refuses to start unless `MAIL_REDIRECT_TO` (a test inbox) is set,
  or `MAIL_ALLOW_REAL_RECIPIENTS=true` is set explicitly for a real deployment.
- Kinds: `case_opened`, `card_blocked` (the handoff email is skipped when this one is sent),
  `handoff_created`. Baseline evaluation runs send nothing. Metric `notifications_total{kind,status}`.

## Consequences

- The SMTP account must be allowed to send as `nicebank@evon.solutions` (alias or send-as permission).
- The customer reply in chat and the email come from the same verified facts, so they cannot disagree.
- Keycloak's password-reset email uses the same server and account: `smtpServer` in the realm file holds
  `${KC_SMTP_*}` placeholders resolved from the container environment at import (docker-compose maps them from
  the same `.env` variables), so no credential is committed. SSL and auth switch on when `EMAIL_PASSWORD` is set.
  The reset demo user `cliente20` gets `MAIL_REDIRECT_TO` as its address; other test users keep `@example.test`.
  Its email theme (`infra/keycloak/themes/nicebank/email`) uses the same design as the backend emails.
