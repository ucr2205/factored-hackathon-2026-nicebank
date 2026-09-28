---
tags: [modulo, backend]
estado: funcionando (simuladas)
dueño: Líder
---

# Herramientas del banco

> [!tip] En simple
> Son las **acciones** que el sistema puede hacer sobre el "banco" (simulado en Postgres). Cada una que escribe
> algo **relee el resultado** para confirmar que pasó. Solo entonces el cliente ve "✅ Verificado".

| Herramienta | Qué hace | Requisito | Cómo se verifica |
|---|---|---|---|
| `find_transactions` | Busca movimientos de **tus** tarjetas por fecha, monto (±2%) y comercio | Sesión válida (RLS) | Solo lectura |
| `find_duplicates` | Busca cobros iguales del mismo comercio en ≤ 2 días | Sesión válida | Solo lectura |
| `open_dispute_case` | Abre el caso (`DSP-00xxxx`), con clave de idempotencia | Confirmación del cliente | Relee el caso creado |
| `block_card` | Bloquea la tarjeta (`BLK-00xxxx`) | Confirmación **+ TOTP** (`acr=2`) | Relee el estado de la tarjeta |
| `create_handoff` | Crea el resumen para el agente humano | Regla de escalamiento | Relee el handoff |
| `suggest_agents` | Propone agentes que hablan el idioma y tienen la especialidad | — | — |
| `amount_usd` | Convierte a USD con la tasa del día | — | Registra la tasa usada |

> [!info] ¿Qué es la idempotencia?
> Si por un error de red el cliente confirma dos veces, **no** se abren dos casos: la clave de idempotencia
> (el id de la acción pendiente) hace que el segundo intento devuelva el mismo caso.

Archivo: `backend/internal/tools/tools.go`. Relacionado: [[Orquestador]] · [[Base de datos y RLS]].
