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

## Las cuatro decisiones posibles

`explain` (el cobro no es definitivo: se explica con el movimiento real) · `auto` (se propone la acción) ·
`escalate` (a humano, a veces con bloqueo primero) · `ineligible` (fuera de plazo o estado inválido → humano).

## Antes de abrir una disputa: `explain_status` (30 sep)

Si el movimiento que el cliente señala **no es un cobro definitivo**, el asistente se lo explica en vez de abrir
un caso o pasarlo a una persona. Se evalúa **antes** que la antigüedad y el monto; gana la primera regla que
coincide. Es la idea central de la [[Visión de producto]]: el 8% de las compras del dataset está en esta situación.

| Regla | Estado | Tipos | Qué hace |
|---|---|---|---|
| `EXPLAIN-REVERSED` | Revertido | todos | "Ya se revirtió, el dinero volvió": no abre caso |
| `EXPLAIN-DECLINED-FRAUD` | Rechazado | cargo no reconocido | "No se te cobró nada, pero alguien pudo intentar usar tu tarjeta": propone bloquearla (con código TOTP) y pasa a fraude |
| `EXPLAIN-DECLINED` | Rechazado | los demás | "No se te cobró nada": no abre caso |
| `EXPLAIN-PENDING` | Pendiente | monto incorrecto, no recibido, cajero | "Aún puede cambiar; escríbeme cuando se confirme" |

Un cargo **pendiente que el cliente no reconoce** (o duplicado) sí se puede disputar, como antes. Si un
`explain_status` nombra un estado final (`Approved`) o un tipo que no existe, el servicio no arranca. En el demo,
`cliente05` tiene un cobro revertido (42,37 USD en Streaming Music) y un intento rechazado (987,65 USD en Electro
Mundo Online).

> [!warning] Equidad
> Ninguna regla puede depender del **segmento, país o acento** del cliente. Los montos se comparan en USD para que
> la misma regla valga igual en México, Colombia y Argentina ([[Decisiones (ADR)]], ADR 0002).

## Pendientes ([[Persona 4 - Evaluación y pitch]])

- [ ] Revisar umbrales y plazos de la v0; mantener estables los `rule_id`
- [ ] Escribir la FAQ en `knowledge/faq/es` y `knowledge/faq/pt`
- [ ] Registrar cada cambio con una nota de versión

Archivos: `policies/disputes.yaml` · `backend/internal/policy/policy.go` (+ `policy_test.go`).
