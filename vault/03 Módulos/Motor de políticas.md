---
tags: [modulo, politicas]
estado: v0 (borrador)
dueño: Persona 4
---

# Motor de políticas

> [!tip] En simple
> Las **reglas del banco** están escritas en un archivo legible (`policies/disputes.yaml`), no dentro de la IA.
> El backend las lee al arrancar y las aplica. Si el archivo está mal escrito, **el servicio no arranca** (mejor
> fallar temprano que decidir mal).

## Qué define por cada tipo de disputa

```yaml
- id: unrecognized_charge
  display_name: { es: "Cargo no reconocido", pt: "Cobrança não reconhecida" }
  eligible_if: { max_age_days: 120, transaction_status: [Approved, Pending] }
  auto_action: open_dispute_case
  max_auto_amount_usd: 500          # en USD con la tasa del día de la transacción
  escalate_if:
    - { rule_id: DISP-ESC-01, condition: amount_over_max, reason: possible_fraud_high_amount,
        suggest_action: block_card, queue: fraud }
```

| Campo | Significa |
|---|---|
| `eligible_if` | Condiciones para resolverlo solo (antigüedad máxima, estado de la transacción) |
| `auto_action` | Qué acción propone si todo está bien |
| `max_auto_amount_usd` | Por encima de este monto, no se resuelve solo |
| `escalate_if` | Cuándo pasa a humano y a qué cola |
| `rule_id` | Identificador que queda en la auditoría como evidencia |

## Las tres decisiones posibles

`auto` (se propone la acción) · `escalate` (a humano, a veces con bloqueo primero) · `ineligible` (fuera de plazo
o estado inválido → humano).

> [!warning] Equidad
> Ninguna regla puede depender del **segmento, país o acento** del cliente. Los montos se comparan en USD para que
> la misma regla valga igual en México, Colombia y Argentina ([[Decisiones (ADR)]], ADR 0002).

## Pendientes ([[Persona 4 - Evaluación y pitch]])

- [ ] Revisar umbrales y plazos de la v0; mantener estables los `rule_id`
- [ ] Escribir la FAQ en `knowledge/faq/es` y `knowledge/faq/pt`
- [ ] Registrar cada cambio con una nota de versión

Archivos: `policies/disputes.yaml` · `backend/internal/policy/policy.go` (+ `policy_test.go`).
