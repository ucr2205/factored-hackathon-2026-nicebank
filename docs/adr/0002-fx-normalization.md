# ADR 0002 — Policy amounts are evaluated in USD using the transaction-date exchange rate

- Status: Accepted
- Date: 2026-09-26

## Context

Transactions are denominated in MXN, COP and ARS (plus USD). Policy thresholds such as "open a dispute
case automatically only below a given amount" must mean the same thing in every country. ARS in particular
moves strongly over the three-year window, so thresholds in local currency would treat customers unequally.

## Decision

- Policy thresholds are defined in USD only.
- Amounts are converted with `daily_exchange_rates` for the **transaction date**. If that date is missing,
  the last available prior rate is used and the fill is flagged (`rate_filled = true`).
- The ETL recomputes `amount_usd` and compares it with the value shipped in `transactions`; mismatches above
  1% are reported in the data-quality report.
- Customers see amounts in their local currency. Audit records store the local amount, the USD amount and the
  rate used (date, pair, source).
- No external FX API is used, so results are reproducible offline.

## Consequences

- One policy file serves all three countries and supports the fairness analysis by country.
- The system depends on the organizer's rate table; gaps and mismatches are surfaced as data-quality issues.
