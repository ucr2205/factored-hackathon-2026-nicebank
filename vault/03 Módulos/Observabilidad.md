---
tags: [modulo, infra, observabilidad]
estado: funcionando
dueño: Líder
actualizado: 2026-10-01
---

# Observabilidad

> [!tip] En simple
> Cuatro formas de "ver" lo que pasa dentro del sistema:
> - **Resumen del supervisor (la app)**: KPIs y gráficas del negocio, para cualquiera del equipo. Empieza aquí.
> - **Trazas (Jaeger)**: el recorrido de *una* conversación paso a paso, con cuánto tardó cada uno.
> - **Métricas (Prometheus)**: los números *generales* en el tiempo (tráfico, escalamientos, latencia, costo) y las
>   alertas.
> - **Auditoría (Postgres)**: el registro permanente de qué se decidió y por qué regla.

| Herramienta | Pregunta que responde | Dónde |
|---|---|---|
| Supervisión → **Resumen** | ¿Cómo le está yendo al asistente? ¿Cuántos casos pasan a una persona? | http://localhost:5173/supervisor (usuario `supervisor01`) |
| Jaeger | ¿Qué pasó en *este* caso y dónde se demoró? | http://localhost:8090/jaeger/ (servicio `disputes-backend`) |
| Jaeger → **Monitor** | ¿Qué operación es lenta o falla más? | http://localhost:8090/jaeger/monitor |
| Prometheus | ¿Cómo va el sistema en el tiempo? ¿Hay alertas? | http://localhost:8090/prometheus/ |
| `audit_events` | ¿Qué regla justificó cada paso? | Consola del agente → Auditoría |

## Resumen del supervisor (la forma más fácil)

En **Supervisión → Resumen** hay un selector de periodo (24 horas, 7 días, 30 días, todo), 8 KPIs y 7 gráficas,
todo leído de la auditoría y de la cola de casos (`GET /api/admin/analytics`). Nunca muestra datos de clientes.

| Qué ves | Qué significa |
|---|---|
| Conversaciones, resueltas sin una persona, pasaron a un especialista | El corazón del pitch: cuánto resuelve solo el asistente |
| Tiempo de respuesta típico y del 5% más lento | p50 y p95 de cada respuesta |
| Casos esperando, tiempo hasta que un especialista toma el caso | Salud de la cola de especialistas |
| Respuestas en el tiempo | Cuántas respuestas por hora o día y cómo terminó cada una |
| Asistente vs. baseline | La comparación que pide el reto (aparece cuando el arnés de evaluación corre el baseline) |
| Qué regla decidió cada respuesta | Las 10 reglas de la política más usadas |
| Hasta dónde llegan las conversaciones | Entendió → encontró el movimiento → propuso → el cliente confirmó → verificado |
| Dónde se va el tiempo | Promedio por paso del turno |

Con **"Ver detalle técnico"** aparecen enlaces directos a Prometheus y a Jaeger.

## Prometheus en 5 enlaces

Prometheus guarda números en el tiempo; no es un tablero. Por eso al abrirlo "no se ve nada": hay que pedirle una
gráfica. Estos enlaces abren varias gráficas a la vez (últimas 6 horas). Las series que empiezan con
`nicebank:` son **reglas de registro** (`infra/prometheus/rules.yml`): cálculos con nombre legible que Prometheus
hace solo cada 15 s.

| Enlace | Qué muestra |
|---|---|
| [El asistente](http://localhost:8090/prometheus/graph?g0.expr=nicebank%3Aturns_by_outcome%3Arate5m&g0.tab=0&g0.range_input=6h&g1.expr=nicebank%3Aescalation_ratio%3A5m&g1.tab=0&g1.range_input=6h&g2.expr=nicebank%3Aresolve_ratio%3A5m&g2.tab=0&g2.range_input=6h) | Respuestas por resultado, % que pasa a una persona y % resuelto (sistema vs baseline) |
| [Tiempos](http://localhost:8090/prometheus/graph?g0.expr=nicebank%3Aturn_latency_seconds%3Ap50_5m&g0.tab=0&g0.range_input=6h&g1.expr=nicebank%3Aturn_latency_seconds%3Ap95_5m&g1.tab=0&g1.range_input=6h&g2.expr=nicebank%3Ahttp_latency_seconds%3Ap95_5m&g2.tab=0&g2.range_input=6h) | p50 y p95 del turno, p95 por ruta HTTP |
| [La cola](http://localhost:8090/prometheus/graph?g0.expr=handoffs_open&g0.tab=0&g0.range_input=6h&g1.expr=handoffs_oldest_wait_seconds&g1.tab=0&g1.range_input=6h&g2.expr=handoffs_by_status&g2.tab=0&g2.range_input=6h) | Casos abiertos por prioridad, el que más espera, casos por estado y resolución |
| [La IA](http://localhost:8090/prometheus/graph?g0.expr=nicebank%3Allm_calls%3Arate5m&g0.tab=0&g0.range_input=6h&g1.expr=nicebank%3Allm_cost_usd%3Aincrease1h&g1.tab=0&g1.range_input=6h&g2.expr=nicebank%3Aml_classify_latency_seconds%3Ap95_5m&g2.tab=0&g2.range_input=6h) | Llamadas a DeepSeek por modelo y resultado, costo por hora, latencia del clasificador |
| [Salud](http://localhost:8090/prometheus/graph?g0.expr=up&g0.tab=0&g0.range_input=6h&g1.expr=nicebank%3Ahttp_error_ratio%3A5m&g1.tab=0&g1.range_input=6h&g2.expr=sum+by+%28kind%2C+status%29+%28increase%28notifications_total%5B1h%5D%29%29&g2.tab=0&g2.range_input=6h) | Servicios arriba, % de errores 5xx, correos enviados o fallidos |

- **Alertas** (menú *Alerts*): backend o clasificador caídos, más de 5% de errores, el 5% más lento sobre 4 s,
  DeepSeek fallando, correos sin entregar y un caso esperando más de 30 minutos. Solo se ven en Prometheus; no
  envían avisos a nadie.
- **Los datos ya no se pierden** al reiniciar: Prometheus guarda 15 días en el volumen `promdata`.
- **Las series existen desde el arranque** (en cero), así que las gráficas aparecen aunque todavía no haya chats.

### Métricas disponibles

| Métrica | Qué mide |
|---|---|
| `chat_turns_total{lang,outcome,mode}` | Turnos por resultado, idioma y modo (sistema/baseline) |
| `chat_turn_duration_seconds` | Duración de cada turno (histograma → p50/p95) |
| `http_requests_total{route,method,status}` | Peticiones por ruta (el patrón, `/api/handoffs/{id}`, nunca la URL real) y código |
| `http_request_duration_seconds{route,method}` | Duración por ruta |
| `tool_calls_total{tool,status}` | Uso de herramientas y fallas de verificación |
| `llm_calls_total{provider,model,op,status}` | Llamadas al LLM: `ok`, `error`, `empty`, `invalid_json` o `cancelled` (extracción descartada a propósito) |
| `llm_tokens_total{provider,direction}` | Tokens del LLM |
| `llm_cost_usd_total{provider,model}` | Gasto en DeepSeek en USD (precios de lista) |
| `llm_speculative_extractions_total{outcome}` | Extracciones lanzadas en paralelo: `used` o `discarded` |
| `notifications_total{kind,status}` | Correos al cliente por tipo y resultado (`sent`, `retry`, `failed`) |
| `handoffs_open{priority}`, `handoffs_oldest_wait_seconds`, `handoffs_by_status{status,resolution}` | La cola de especialistas, leída de Postgres en cada lectura de Prometheus (solo conteos) |
| `pii_mask_degraded_total` | Turnos en que no se pudieron descifrar los nombres y el enmascarado usó solo patrones |
| `ml_classify_total{label,abstain}`, `ml_classify_seconds` | Clasificaciones del ml-service y su latencia |
| `traces_span_metrics_*` | Tasa, errores y duración por operación, calculados por el colector a partir de las trazas |

> [!info] p50 y p95, en simple
> Si ordenas todos los tiempos de respuesta de menor a mayor, el **p50** es el del medio (el tiempo *típico*: la
> mitad tardó menos) y el **p95** es el que deja por debajo al 95% (el tiempo de las respuestas *más lentas*). Se
> reporta el p95 porque un promedio puede esconder que 1 de cada 20 clientes espera mucho.

## Cómo leer y filtrar en Jaeger

Cada mensaje del chat es **una traza**. Desde el 1 de octubre se lee así:

- La raíz se llama como la ruta: `POST /api/chat`, `POST /api/chat/confirm`, `GET /api/handoffs/{id}`. Antes todas
  se llamaban solo `POST` o `GET`.
- Debajo está `chat.turn` y los pasos `step.understand`, `step.extract`, `step.policy`… **con su duración real**
  (antes duraban cero). También aparecen `ml.classify` (el clasificador) y `llm.extract`/`llm.pick`/`llm.compose`
  (DeepSeek, con modelo y versión del prompt, **sin el texto**).

**Filtrar** (pestaña *Search*, campo *Tags*, formato `clave=valor`):

| Quiero ver… | Tags |
|---|---|
| Los turnos que pasaron a una persona | `chat.outcome=escalate` |
| Los que decidió una regla concreta | `chat.rule_id=DISP-ESC-01` (o `EXPLAIN-REVERSED`, `SEC-INJ-01`…) |
| Un tipo de disputa | `chat.dispute_type=duplicate_charge` |
| Solo portugués o solo el baseline | `chat.lang=pt` · `chat.mode=baseline` |
| Una conversación concreta | `chat.session_id=<id>` (está en la auditoría de la consola) |
| Los que fallaron | `error=true` |

Enlaces listos: [escalamientos de las últimas 24 h](http://localhost:8090/jaeger/search?service=disputes-backend&lookback=24h&limit=50&tags=%7B%22chat.outcome%22%3A%22escalate%22%7D) ·
[trazas con error](http://localhost:8090/jaeger/search?service=disputes-backend&lookback=24h&limit=50&tags=%7B%22error%22%3A%22true%22%7D) ·
[chats de más de 3 s](http://localhost:8090/jaeger/search?service=disputes-backend&lookback=24h&limit=50&operation=POST%20/api/chat&minDuration=3s).

**Pestaña Monitor:** tasa de llamadas, % de errores y duración (p50/p75/p95) por operación, sin buscar trazas una
por una. Elige el servicio `disputes-backend`. Los datos salen de las *span metrics* que el colector calcula y
Prometheus guarda.

> [!example] Lo que Jaeger mostró el 1 oct
> Un turno de cliente03 tardó **13,6 s**: `llm.extract` con DeepSeek Flash falló a los 8 s y el respaldo Pro tardó
> 5,6 s más. Sin trazas legibles esto no se veía. Vale revisar el tiempo de espera de Flash ([[LLM]]).

> [!warning] Sin datos personales
> Las trazas y métricas solo llevan ids, tipos, reglas y tiempos. Además, el colector **borra por patrón**
> cualquier atributo cuyo nombre suene a dato personal (correo, nombre, documento, teléfono, tarjeta,
> `customer_ref`, contenido del prompt, cookies…) y la IP de red, por si alguno se cuela
> (`infra/otel/config.yaml`). La versión del prompt (`llm.prompt_version`) sí se conserva: no es contenido.

## Logs

Los logs del backend son JSON, una línea por evento, y cada una lleva `request_id` y `trace_id`: el mismo
`trace_id` que buscas en Jaeger. Hay una línea por petición HTTP, una por turno del chat y una por correo. El
detalle está en [[Backend (Go)#Logs]].

```bash
docker compose logs -f backend                            # en vivo
docker compose logs backend | grep '"level":"ERROR"'      # solo errores
docker compose logs backend | grep <request_id>           # lo que pasó en una petición concreta
```

Grafana se descartó el 1 oct (el líder prefirió no sumar otro servicio): el Resumen del supervisor cubre los
números del negocio y Prometheus/Jaeger los técnicos. Relacionado: [[Pruebas de carga con JMeter]].
