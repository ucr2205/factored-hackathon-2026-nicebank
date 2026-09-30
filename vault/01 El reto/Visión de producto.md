---
tags: [producto, vision, pitch, enfoque]
actualizado: 2026-09-30
---

# Visión de producto

> [!tip] En una frase
> Un cliente describe **a medias** un cobro que no reconoce, y en **menos de un minuto** tiene su disputa abierta
> y verificada, una explicación con su propio movimiento, o un especialista con el caso completo. **Hoy eso
> toma ~15 días.**

Esta página existe porque los organizadores nos lo pidieron (30 sep): *pensar como constructores de producto, no
de funcionalidades*. Antes de agregar algo, debe responder a las tres preguntas de abajo. Si no, no entra.

## Las tres preguntas

| Pregunta | Nuestra respuesta | De dónde sale |
|---|---|---|
| **¿Qué problema resolvemos?** | Las disputas por cobros con tarjeta son el **40% de los reclamos** (27.133 en 3 años), tardan **~15 días**, el **20%** sale fuera de plazo y el **75%** sigue abierto | EDA del Gate 1 (`docs/eda_findings.md`) |
| **¿Quién lo sufre?** | El cliente que ve un cobro raro y lo describe a medias ("el de Uber del martes, como 45 mil"), en **español o portugués**; y el especialista, que recibe casos incompletos y vuelve a preguntar | [[Datos del proyecto]] |
| **¿Qué es lo distinto?** | El asistente **ubica el cobro exacto en el historial del propio cliente** y actúa en segundos. El LLM solo propone; el código decide, verifica cada acción y **nunca mueve dinero** | [[El viaje de un mensaje]] |

## Lo que hace el producto (y nada más)

1. **Encuentra el movimiento** con lo que dice el cliente (monto, fecha, comercio), aunque lo diga a medias.
2. **Lo explica si no es un cobro definitivo** (nuevo, 30 sep). El 8% de las compras con tarjeta del dataset no lo
   es: 2,0% pendientes, 5,0% rechazadas, 1,0% revertidas. En vez de abrir una disputa o molestar a un
   especialista, el asistente responde con el movimiento real: *"esa compra fue rechazada, no se te cobró nada"*.
   Si alguien intentó una compra que el cliente no reconoce y fue rechazada, además **propone bloquear la
   tarjeta** y pasa el caso a fraude. Reglas `EXPLAIN-*` en [[Motor de políticas]].
3. **Abre la disputa verificada** cuando el caso es elegible, siempre con la confirmación del cliente.
4. **Escala con el expediente completo** cuando no puede resolverlo solo: el especialista no vuelve a preguntar.

## Cómo lo vamos a demostrar (números del pitch)

Todo contra el **baseline** (hoy: toda disputa pasa a una persona), con los casos de [[Evaluación]]:

| Métrica | Qué muestra |
|---|---|
| Tiempo hasta tener el caso abierto | 15 días → segundos en los casos elegibles |
| % de veces que acierta el cobro correcto | Que "ubicar el cobro" funciona de verdad |
| Disputas y escalamientos evitados (reglas `EXPLAIN-*`) | Casos que no necesitaban ni disputa ni persona |
| % de expedientes completos al especialista | Que nadie vuelve a preguntar |
| Acciones inseguras | Debe ser **0** |

## Qué NO hacemos (congelado el 30 sep)

| Idea | Por qué no |
|---|---|
| "Mis disputas", correo al resolver, cerrar casos en la consola | No cambian la historia del pitch |
| Detectar suscripciones o personalizar por patrón de gasto | En el dataset no hay señal: los montos son aleatorios (misma distribución en los 24 comercios) y solo el 0,2% de los pares cliente-comercio se repite estable mes a mes. El jurado lo notaría |
| Laya, Redis | No resuelven un problema que tengamos |
| ETL de `digital_events` | El producto no lo usa; los organizadores permiten no usar todo el dataset **si explicamos por qué** |
| Más trabajo en supervisión, JMeter, Swagger o logs | Ya están; van en **una** diapositiva de "listo para producción" |

## Datos inventados (`team_generated`) y la evaluación

El dataset no trae ninguna frase real de disputa, así que las frases de los clientes las escribe el equipo. Un
organizador dijo que los datos inventados se pueden usar *"if it's not used for testing"*. Para cuidarnos:

- Cada caso de evaluación se ancla en **clientes y transacciones reales del dataset** (comercio, monto, fecha y
  estado reales). Solo la frase del cliente es inventada, y la respuesta esperada se deduce de la fila real.
- Los únicos movimientos inventados son las 5 fixtures del demo (`TRX-DEMO-*`, `origin = team_generated`),
  y no se usan para medir.
- Pendiente: que el organizador confirme este enfoque (el líder tiene el mensaje listo para enviar).

Relacionado: [[El reto en simple]] · [[Cómo nos evalúan]] · [[Estado del proyecto]] · [[Persona 4 - Evaluación y pitch]]
