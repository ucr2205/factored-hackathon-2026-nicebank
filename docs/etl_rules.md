# ETL Sanitization Rules (raw → silver contract)

The rules the pipeline (`etl/pipeline/`, `make etl`) applies to every load, agreed on 2026-09-29.
Sources: the organizer's *LATAM_Bank_Complete_Data_Dictionary* (types, NOT NULL, UNIQUE, domains,
ranges), the measured findings in [`data_quality_report.md`](data_quality_report.md), and team
decisions where the dictionary is silent. Affected counts are from dataset v1.0.0.

Five actions, from least to most drastic:

| Action | Meaning |
|---|---|
| **Correct** | Safe, invented-nothing fixes: types, trimming, null tokens, word-for-word standardization, recomputations |
| **Null + flag** | The value is wrong but the record is real and referenced: value removed, boolean flag set |
| **Quarantine** | The row breaks something mandatory and unfixable; it moves to `data/quarantine/<table>/` with `rule_id`, never silently deleted |
| **Flag only** | Business incoherence the generator created; removing rows would destroy the dataset |
| **Guard** | Zero cases today; the rule stays active for future deliveries |

Two invariants: **never invent a value, never merge two people**; and every action is counted in the
lineage (`etl_state.duckdb`: `etl_runs`, `quality_findings`) under the run that applied it.

## A. Correct (standardization)

| # | Rule | Source | Affected |
|---|---|---|---|
| A1 | Trim whitespace; null-like text (`None`, `nan`, `NULL`, `N/A`, …) → NULL | finding | guard |
| A2 | Cast every column to its dictionary type; `response_code` stays text (leading zeros) | dictionary | all |
| A3 | Canonical country **"Mexico"** everywhere ("México" → "Mexico") | dictionary + team | ~2.4M rows |
| A4 | Canonical English values: Pasaporte→Passport, the 8 product types, Urbana→Urban, reason categories, sentiments | dictionary | ~1.1M rows |
| A5 | Derive what is certain: `nps_category` from the score; `amount_usd` = amount × transaction-date rate (ADR 0002; shipped value kept as `amount_usd_source`, `fx_rate_missing` flagged); `is_international` (raw unaccented "Mexico" = foreign purchase); `event_date` from the event timestamp | dictionary + ADR 0002 | 3.3k surveys, 4.4M txns |
| A6 | Business dates come from the event timestamp, never `process_date` (06:00/08:00 day cutoff) | finding | 25–34% of fact rows |
| A7 | Cards keep only `card_last4` + `card_brand`; `product_number` never reaches silver | hard rule 3/5 | 140k cards, 400k products |
| A8 | Three canonical values extend the dictionary, which omits them: **Very Positive, Retention, Web** | team | 43k rows |

## B. Uniqueness (one identifier → one person/entity)

| # | Key | Source | Affected | Policy |
|---|---|---|---|---|
| B1 | `customers.document_number` | dictionary UNIQUE | 0 | guard (keep_first by registration_date) |
| B2 | `service_agents.employee_code` | dictionary UNIQUE | 13 pairs | first hired keeps it; later NULL + `employee_code_conflict` |
| B3 | `products.product_number` | dictionary UNIQUE | 6 pairs | first opened keeps it; later NULL + `product_number_conflict` |
| B4 | `branches.branch_code` | dictionary UNIQUE | 0 | guard |
| B5 | Customer email | team | 79,930 customers | NULL for **all** sharers + `email_shared` (no way to pick the owner; a bank notice to the wrong person is a data leak). Demo users get unique `clienteNN@example.test` at load |
| B6 | Agent email | team | 24 agents | first hired keeps it + `email_conflict` (corporate email is assigned at hire) |
| B7 | Phones (mobile, landline; across customers and agents) | team | 16 + 10 customers, 8 vs agents | shared among customers → NULL all + flag; customer phone equal to an agent's → the agent keeps it, customer NULL + `phone_matches_agent` |
| B8 | Same PK re-delivered → latest `process_date` wins (late arrivals); same content under a new PK → quarantine `dedup.content_duplicate` | dictionary (~2% announced) | 0 today | guard |

Not merged (validated person by person): the 19 customer pairs sharing surname+birth date+city and the
homonymous agents — names, documents and emails differ; they are distinct people.

## C. Quarantine (mandatory and unfixable)

| # | Rule | rule_id | Affected |
|---|---|---|---|
| C1 | NULL primary key | `contract.<pk>.not_nullable` | 0 (guard) |
| C2 | NOT NULL column whose value does not parse as its type | `cast.<col>` | 0 (guard) |
| C3 | Value outside a closed dictionary domain (post-standardization) | `contract.<col>.isin` | 0 (guard) |
| C4 | Out of range: credit_score 300–850, fraud_score 0–100, scores, amounts ≥ 0, rates > 0 | `contract.<col>.*` | 0 (guard) |
| C5 | Content duplicate under a different id | `dedup.content_duplicate` | 0 (guard) |

Quarantined rows keep their **original raw text values** plus `rule_id`, `reason`, `stage`, `run_id`.

## D. Null + flag

| # | Rule | Flag | Affected |
|---|---|---|---|
| D1 | Coordinates near (0, 0) → NULL | `coords_invalid` | 167 branches, 408k txns |
| D2 | `registration_branch_id` / `assigned_branch_id` pointing to a non-existent branch (dictionary FK broken at ~100%: not enforced as FK, rule D4 of the report) | `branch_unresolved` | 149,995 customers, 831 agents |
| D3 | Complaint currency without amount → NULL currency; amount without currency → flagged, no conversion | `currency_removed_no_amount`, `amount_without_currency` | 1,065 / 1,040 |
| D4 | Sentiment "Muy Positivo" → **Very Positive** (kept, dictionary extension A8) | — | 18,973 |

## E. Flag only (generator incoherences — never deleted)

`quality_findings` counts every one per run; per-row flags where consumers need them:
product opened before its customer registered (~200k), transaction before its product opened (~828k,
`predates_product`), expired-but-active cards (~57k, `expired_active_card`), ATM channel on
non-withdrawals (~1.0M), purchases without merchant (~54k), escalated-yet-resolved calls (~52k,
`escalated_and_resolved`), complaint date/status mismatches (~3k), login/logout contradictions in
digital events (~2.2M, `action_event_mismatch`), registered minors (3.1k), transcript
`duration_seconds` NULL although the dictionary says NOT NULL (24k, `dict.duration_seconds_null`).

## Normalization (targeted 3NF in silver)

Functional dependencies measured at 100% and factored out; the operational loader re-joins them:

| Removed from | Column | Lives in |
|---|---|---|
| `call_center_interactions` | `contact_reason` (byte-identical to `reason_category`, 686k rows) | dropped |
| `complaints` | `subcategory` (1:1 with `category`) | `dim_categories` |
| `customers`, `branches` | `state` (city → state) | `dim_cities` |
| `transactions` | `merchant_category` (merchant_name → category) | `dim_merchants` |

Documented intentional denormalization (kept): `transactions.customer_id` (derivable via product, kept
for RLS and query speed; owner consistency verified at 0 mismatches), survey question texts.

## Dictionary violations found in dataset v1.0.0 (reported, not silently fixed)

NPS scores span 2–7 (no Promoters exist), CSAT max is 4 of 5; no MXN products or transactions exist;
`origin_interaction_id` is always empty; announced ~2% duplicates and late arrivals are absent;
`transactions.transaction_country` uses unaccented "Mexico" as an international marker.
