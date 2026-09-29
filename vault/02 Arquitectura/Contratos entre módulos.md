---
tags: [arquitectura, contratos]
---

# Contratos entre módulos

> [!tip] ¿Qué es un contrato?
> Un **acuerdo de formato** entre dos piezas: "yo te mando esto, tú me devuelves aquello". Mientras se respete,
> cada persona puede cambiar su pieza por dentro sin romper la de los demás. **Se congelan en el Gate 1 (28 sep).**
> Cambiar uno después exige avisar al líder.

| # | Contrato | Qué define | Archivo | Dueño |
|---|---|---|---|---|
| C1 | Base de datos | Tablas del sistema y reglas de RLS | `infra/postgres/init/01_schema.sql`, `02_rls.sh` | [[Líder]] (P2 lo llena) |
| C2 | ml-service | `POST /classify {text, lang}` → `{label, confidence, abstain, model_version}` · `POST /embed {texts, kind}` → vectores de 384 | `ml/service/app.py` | [[Persona 3 - IA y ML]] |
| C3 | Políticas | Tipos de disputa, montos límite en USD, elegibilidad, ids de reglas | `policies/disputes.yaml` | [[Persona 4 - Evaluación y pitch]] |
| C4 | Casos de prueba | Formato JSONL de cada caso | `eval/cases/` (por crear) | [[Persona 4 - Evaluación y pitch]] |
| C5 | Handoff | Lo que recibe el agente humano | `docs/api/contracts.md` | [[Líder]] |
| C6 | Taxonomía | Lista de tipos de disputa | política + clasificador | P2 + P3 + P4 |

## C6 — Tipos de disputa

`unrecognized_charge` (no reconocido) · `duplicate_charge` (duplicado) · `wrong_amount` (monto incorrecto) ·
`not_received` (no recibido) · `atm_cash_not_dispensed` (cajero no entregó) · `card_lost_stolen` (perdida o
robada) · `other_in_scope` · `out_of_scope` (préstamos, inversiones…).

Cómo se mapean las categorías de reclamo del dataset (decidido el 28 sep, `analysis/mappings/contact_reason_to_flow.csv`):

| Categoría del reclamo | Tipo C6 |
|---|---|
| `Transactions` — "Cargo no reconocido" | `unrecognized_charge` |
| `Fees` — "Cobro indebido" | `wrong_amount` |
| `Technical`, `Service`, `Branch` | `out_of_scope` |

`other_in_scope` no tiene reglas en `policies/disputes.yaml`: el backend lo trata como tipo desconocido, pregunta qué
pasó y, al llegar al límite de preguntas, pasa el caso a un humano.

## C4 — Un caso de prueba

```json
{"id":"PT-AMB-007","lang":"pt","segment":"Basic","country":"Colombia","customer_user":"cliente07",
 "origin":"team_generated","turns":["Me cobraram duas vezes, não sei qual"],
 "expected":{"outcome":"clarify","action":null,"dispute_type":"duplicate_charge","must_not":["open_dispute_case"]},
 "tags":["ambiguous","multilingual"]}
```

## Resultados posibles de cada turno

`resolve` (resuelto) · `clarify` (pregunta) · `abstain` (se abstiene) · `escalate` (pasa a humano) ·
`confirm` (pide confirmación). La API completa está en `docs/api/contracts.md` del repo.
