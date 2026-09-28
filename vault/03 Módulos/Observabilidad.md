---
tags: [modulo, infra, observabilidad]
estado: funcionando
dueño: Líder
---

# Observabilidad

> [!tip] En simple
> Tres formas de "ver" lo que pasa dentro del sistema:
> - **Trazas (Jaeger)**: el recorrido de *una* conversación paso a paso, con cuánto tardó cada uno.
> - **Métricas (Prometheus)**: los números *generales* (cuántos turnos, cuántos escalamientos, latencia).
> - **Auditoría (Postgres)**: el registro permanente de qué se decidió y por qué regla.

| Herramienta | Pregunta que responde | Dónde |
|---|---|---|
| Jaeger | ¿Qué pasó en *este* caso y dónde se demoró? | http://localhost:16686 (servicio `disputes-backend`) |
| Prometheus | ¿Cómo va el sistema en general? | http://localhost:9090 |
| `audit_events` | ¿Qué regla justificó cada paso? | Consola del agente → Auditoría |

## Métricas disponibles

| Métrica | Qué mide |
|---|---|
| `chat_turns_total{lang,outcome,mode}` | Turnos por resultado, idioma y modo (sistema/baseline) |
| `chat_turn_duration_seconds` | Duración de cada turno (histograma → p50/p95) |
| `tool_calls_total{tool,status}` | Uso de herramientas y fallas de verificación |
| `llm_tokens_total{provider,direction}` | Tokens del LLM (costo) |
| `llm_calls_total{provider,model,op,status}` | Llamadas al LLM por modelo y resultado: `ok`, `error`, `empty`, `invalid_json` o `cancelled` (extracción descartada a propósito) |
| `llm_speculative_extractions_total{outcome}` | Extracciones lanzadas en paralelo con la clasificación: `used` (se usaron) o `discarded` (el mensaje no era una disputa) |
| `notifications_total{kind,status}` | Correos al cliente por tipo y resultado (`sent`, `retry`, `failed`) |
| `pii_mask_degraded_total` | Turnos en que no se pudieron descifrar los nombres y el enmascarado usó solo patrones |
| `ml_classify_total{label,abstain}` | Clasificaciones del ml-service |

> [!info] p50 y p95, en simple
> Si ordenas todos los tiempos de respuesta de menor a mayor, el **p50** es el del medio (el tiempo *típico*: la
> mitad tardó menos) y el **p95** es el que deja por debajo al 95% (el tiempo de las respuestas *más lentas*). Se
> reporta el p95 porque un promedio puede esconder que 1 de cada 20 clientes espera mucho. Ejemplo real con
> DeepSeek: chat p50 970 ms y p95 1.299 ms ([[Pruebas de carga con JMeter]]).

En Jaeger, cada llamada al LLM aparece como un tramo `llm.extract`, `llm.pick` o `llm.compose` con el modelo, la
versión del prompt y los tokens, **sin el texto**. Los correos aparecen como `notify.send_email`.

> [!warning] Sin datos personales
> Las trazas y métricas solo llevan ids, tipos, reglas y tiempos. Además, el colector de OpenTelemetry **borra por
> patrón** cualquier atributo cuyo nombre suene a dato personal (correo, nombre, documento, teléfono, tarjeta,
> `customer_ref`, texto del prompt, cookies…) y la IP del cliente, por si alguno se cuela
> (`infra/otel/config.yaml`).

Pendiente opcional: un dashboard de Grafana para el video. Relacionado: [[Pruebas de carga con JMeter]].
