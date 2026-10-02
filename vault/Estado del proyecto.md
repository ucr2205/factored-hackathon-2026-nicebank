---
tags: [estado, resumen, seguimiento]
actualizado: 2026-10-01
---

# Estado del proyecto

> [!tip] Para qué sirve esta página
> Es la foto del proyecto **hoy**: qué ya funciona, qué falta, qué nos preocupa y qué decisiones esperan al
> líder. Se actualiza **cada vez que cambia algo** en el código, la infraestructura o el plan. Si algo aquí no
> coincide con lo que ves en el repo, el repo manda y esta página se corrige.

**Hoy:** jueves 1 oct 2026 (día 6 de 10) · **Siguiente:** Gate 3, viernes 2 oct (todo construido + primera evaluación completa) ·
**Foco del producto:** [[Visión de producto]] (qué construimos y qué quedó fuera) ·
**Congelamiento:** domingo 4 oct 20:00 · **Entrega:** lunes 5 oct. Ver [[Calendario y gates]].

## Semáforo por área

| Área | Estado | En una línea | Más detalle |
|---|---|---|---|
| Chat del cliente y orquestador | ✅ Listo | Entiende, decide con reglas, actúa con confirmación, verifica y escala | [[Orquestador]] |
| **Explicar el cobro antes de disputar** | ✅ Nuevo (30 sep) | Revertido, rechazado o pendiente: lo explica con el movimiento real; un intento rechazado no reconocido propone bloquear la tarjeta | [[Motor de políticas]] |
| Inteligencia artificial (LLM) | ✅ Listo | DeepSeek Flash real, Pro de respaldo y reglas como último recurso | [[LLM]] |
| Identidad y seguridad | ✅ Listo | Referencia opaca, nombres cifrados, TOTP (ahora en una ventana sobre el chat), RLS, endurecimiento | [[Seguridad]] |
| Correos al cliente | ✅ Listo | 3 correos con diseño NiceBank + recuperación de contraseña, mismo servidor | [[Notificaciones por correo]] |
| Consola del agente y supervisión | ✅ Listo | En español claro; **Resumen con 8 KPIs y 7 gráficas**; barra burdeos y menos blanco | [[Frontend]] |
| Logs, trazas y métricas | ✅ Listo | Prometheus con reglas, alertas y datos persistentes; Jaeger legible, filtrable y con pestaña Monitor | [[Observabilidad]] |
| Documentación del API | ✅ Listo | Swagger UI en http://localhost:8081/api/docs | [[Backend (Go)]] |
| Pruebas | 🟡 Parcial | 50 pruebas en Go, smoke 24/24, JMeter sin errores; faltan pruebas de integración | [[Estrategia de pruebas]] |
| Clasificador de casos | 🔴 Provisional | Sigue siendo por palabras clave | [[ml-service (clasificador)]] |
| Datos y ETL | ✅ Listo | **Pipeline raw → silver + loader**: el sistema ya carga el dataset completo saneado (150k clientes, 4,4M transacciones); falta solo el caso de negocio del pitch | [[ETL y calidad de datos]] |
| **Evaluación (sistema vs baseline)** | 🔴 **Falta** | Sin arnés ni casos held-out: es entregable obligatorio | [[Evaluación]] |
| Entregables (README, slides, video) | 🔴 Falta | Aún no empiezan | [[Persona 4 - Evaluación y pitch]] |
| Despliegue | 🟡 Casi | Configuración lista para **https://hackathon.evon.solutions** (`deploy/evon/`); falta entregar el volcado de datos y la `PII_KEY` | [[Infraestructura]] |

## Lo que ya funciona

- **Gateway con rutas (2 oct):** una sola entrada local (`http://localhost:8090`, el mismo
  esquema de rutas que el nginx del servidor en `deploy/evon/`) con la app en `/`, el API en `/api` y **Jaeger, Prometheus y Mailpit en `/jaeger`, `/prometheus` y
  `/mail` detrás de usuario y contraseña** (`make env` los crea). Probado el 2 oct: sin login dan 401, con login abren, y `/metrics` no queda expuesto. Guía de pruebas completa en Claude Docs ("Guía de pruebas NiceBank").
- **Observabilidad que se entiende (1 oct).** Prometheus "no mostraba nada" porque no es un tablero y no tenía
  reglas, métricas HTTP ni datos guardados. Ahora tiene 13 reglas con nombre `nicebank:*`, 7 alertas, métricas por
  ruta, costo de DeepSeek y la cola de casos, guarda 15 días y trae [[Observabilidad#Prometheus en 5 enlaces|5 enlaces
  listos]]. En Jaeger las trazas se llaman como la ruta (`POST /api/chat`), cada paso tiene su duración real, se
  ven las llamadas al clasificador y se puede filtrar por resultado, regla, tipo de disputa o idioma; la pestaña
  **Monitor** muestra tasa, errores y duración por operación. Grafana se descartó.
- **Código 2FA sin salir de la página (1 oct):** ventana sobre el chat desenfocado con la página de código de
  Keycloak; si no carga, cae al flujo anterior. Probado de punta a punta con `cliente05` (bloqueo verificado sin
  recargar) y con Cancelar.
- **Resumen del supervisor (1 oct):** periodo de 24 h a todo, KPIs (resueltas sin una persona, escalamientos,
  tiempos, cola, bloqueos, correos) y gráficas (respuestas en el tiempo, asistente vs baseline, reglas, embudo,
  motivos de escalamiento, tiempo por paso, idioma), desde `GET /api/admin/analytics`.

- **Foco de producto (30 sep).** Los organizadores pidieron pensar como constructores de producto. La frase:
  *un cliente describe a medias un cobro que no reconoce y en menos de un minuto tiene su disputa abierta y
  verificada, una explicación con su propio movimiento o un especialista con el caso completo; hoy toma ~15 días*.
  Qué entra y qué no, en [[Visión de producto]].
- **Explica el cobro antes de abrir una disputa** (reglas `EXPLAIN-*`): el 8% de las compras con tarjeta del
  dataset no es un cobro definitivo (2% pendientes, 5% rechazadas, 1% revertidas). Antes esas iban a un
  especialista; ahora el asistente responde con el movimiento real. Demo con `cliente05`.

- **Demo completo de punta a punta** en español y portugués: disputa normal, pedido ambiguo o fuera de alcance,
  y escalamiento con código TOTP, bloqueo de tarjeta y caso estructurado para un especialista.
- **DeepSeek conectado.** En 16 mensajes de prueba acertó el 100% de montos y comercios y el 93% de fechas,
  con ~1 s de respuesta y fracciones de centavo por mensaje. La extracción corre **en paralelo** con el
  clasificador y se cancela si el mensaje no es una disputa.
- **Fechas sin año** ("23/12") ya se entienden como la última vez que ocurrieron; si no encuentra el
  movimiento, el asistente dice qué buscó.
- **Identidad protegida:** el sistema consulta las filas del cliente sin saber quién es; el agente solo ve el
  nombre al tomar el caso, y queda auditado.
- **Correos reales** desde `nicebank@evon.solutions` (redirigidos a la bandeja de prueba), con logo y marca de
  tarjeta, en el idioma de la conversación.
- **Consola y supervisión legibles:** auditoría en español, nombres de cola, reglas explicadas, prioridad con
  tiempo de espera, nueva barra de navegación.
- **Logs de verdad:** una línea por petición (ruta, estado, duración, IP, rol, `request_id`, `trace_id`), una
  por turno del chat y una por correo enviado; errores con `request_id` para encontrarlos rápido.
- **Swagger** con los 14 endpoints, ejemplos y botón *Authorize*; una prueba falla si una ruta queda sin
  documentar.
- **Repo en GitHub** (privado) con commits hechos por opencode y este vault dentro, en `vault/`.
- **Perfilado de calidad de las 13 tablas** (`make profile` → `docs/data_quality_report.md`): explica las
  desviaciones de filas, mide vacíos, duplicados, llegadas tardías, huérfanos y `amount_usd`, y deja 9 reglas
  para el ETL. Resumen en [[Datos del proyecto#Lo que encontró el perfilado]]. Modelo de datos: [[Modelo ER]].
- **EDA del Gate 1** (`make eda` → `docs/eda_findings.md`): el 40% de los reclamos son disputas por cargos y
  tardan ~15 días con 20% fuera de SLA, así que **se confirma el flujo**. Pero los datos no traen frases reales de
  disputa ni permiten ligar un reclamo con su transacción. Resumen en [[Datos del proyecto#Lo que dice el EDA del Gate 1]].
- **ETL completo** (`make etl`, ~58 min con `digital_events`): raw → silver con contratos por columna, estandarización al inglés del
  diccionario, `amount_usd` recalculado, deduplicación en 3 niveles, unicidad de correos/teléfonos/códigos,
  cuarentena con motivo, linaje y marca de agua incremental; 8 pruebas con fixture de llegada tardía
  (`make test-etl`). Reglas en `docs/etl_rules.md`, frescura en `docs/freshness_policy.md`.
- **`make seed` ahora carga TODO el dataset** desde silver (`etl/load_postgres.py`): 150.000 clientes con identidad
  cifrada, 400.000 productos y 4,4 M transacciones; los mismos `cliente01–20` de siempre en Keycloak, con correos
  de prueba únicos `clienteNN@example.test`.

## Qué falta, por prioridad

1. 🔴 **Arnés de evaluación** con ~200 casos held-out (ES/PT, normal, ambiguo, humano, adversarial), métricas
   del sistema contra el baseline con intervalos de confianza, p50/p95 y costo. → [[Persona 4 - Evaluación y pitch]]
2. 🔴 **Clasificador real** que reemplace las palabras clave (baselines, TF-IDF, embeddings; Laya se descartó el 30 sep).
   ⚠️ **Su guía se reconfiguró el 29 sep**: sin texto de disputas en el dataset, el corpus es
   `team_generated` (ES/PT) con lotes separados de la evaluación; las transcripciones solo dan ejemplos
   fuera de alcance. → [[Persona 3 - IA y ML]]
3. 🟢 **Datos:** ~~reporte de calidad~~, ~~EDA del Gate 1~~, ~~ETL raw → silver~~ y ~~loader a Postgres~~
   (hechos); queda el caso de negocio del pitch (`analysis/03_business_case.py`). → [[Persona 2 - Datos]]
4. 🔴 **Entregables:** README, `docs/architecture.md`, `docs/production_gap.md`, 4–6 slides y video.
5. ⚪ ~~**Producto:** "Mis disputas", cerrar casos en la consola, correo al resolver~~ → **fuera del alcance**
   (30 sep), no cambian la historia del pitch. Ver [[Visión de producto#Qué NO hacemos (congelado el 30 sep)]].
6. 🟡 **Pruebas de integración en Go:** aislamiento RLS, expiración de sesión y fallas de herramientas.
7. 🟡 **Despliegue:** URL pública (enlaces y logo de los correos), quitar el cliente `eval-harness` y los
   usuarios de prueba, gestor de secretos, apagar Swagger (`DOCS_ENABLED=false`).

## Decisiones que esperan al líder

- [ ] Enviar a los organizadores los dos mensajes preparados el 30 sep: a **Diego**, confirmar que la evaluación
  anclada en filas reales con frases `team_generated` es aceptable; a **André**, la visión del producto.
- [ ] Enviar la **prueba real del correo de recuperación** con `cliente20`.
- [ ] **Logos de tarjeta:** theSVG para las tres marcas (recomendado) o Flaticon con atribución + acuerdo de
  Mastercard.
- [ ] Qué hacer con la línea `Co-Authored-By` en los 11 commits antiguos (dejarlos o reescribir historia).
- [ ] Limpiar la cola de casos de prueba (`make seed`): hay casos "Revisión humana (baseline)" creados por
  pruebas.
- [ ] **Gate 1:** confirmar el flujo de disputas (el EDA lo recomienda, ver [[Datos del proyecto#Lo que dice el EDA del Gate 1]]).
- [x] **Taxonomía C6** (P2 + P3 + P4): "Cobro indebido" → `wrong_amount` (decidido el 28 sep; ver
  `analysis/mappings/contact_reason_to_flow.csv`).

## Riesgos

| Riesgo | Qué hacemos |
|---|---|
| La evaluación empieza tarde y no hay números para el jurado | Es la prioridad 1; el `scripts/smoke_chat.py` ya sirve de base |
| El clasificador por palabras clave falla en mensajes reales | P3 entrena uno de verdad; mientras, el sistema pregunta cuando duda |
| DeepSeek se cae o tarda | Pro de respaldo y reglas locales; el cliente nunca se queda sin respuesta. ⚠️ El 1 oct Jaeger mostró un turno de 13,6 s: Flash falló a los 8 s y Pro tardó 5,6 s más. Revisar el tiempo de espera de Flash (P3) |
| Los datos traen 84–88% de las filas anunciadas | ✅ Explicado en el reporte de calidad: el faltante está repartido parejo en el tiempo, no son datos por llegar |
| No hay ningún cargo duplicado real en los datos | El tipo `duplicate_charge` se demuestra y evalúa con casos `team_generated` (P4) |
| Un reclamo no se puede ligar a su transacción (`affected_product_id` ajeno, montos reclamados al azar) | La transacción se busca con lo que dice el cliente en el chat, como ya hace el backend |
| No hay frases reales de disputa en los datos (las transcripciones son 2 plantillas de saldo, sin portugués) | P3 entrena y P4 evalúa con frases `team_generated` en ES y PT |
| 79.930 clientes comparten su correo con otro cliente (el generador lo arma con inicial + apellido) | Un aviso "a un cliente" llegaría a otras personas: hoy no pasa porque con servidor real todo va a `MAIL_REDIRECT_TO`; hay que anotarlo en la brecha a producción (P4) |
| El ETL completo necesita mucho disco (DuckDB deja temporales de varios GB si se corta) | Antes de `make etl`, dejar ≥ 15 GB libres; si se cortó, borrar los `*.tmp` de DuckDB. Ver [[Problemas comunes]] |
| Un organizador dijo que los datos inventados se pueden usar *"if it's not used for testing"*, y nuestras frases de evaluación son `team_generated` | Cada caso se ancla en una transacción real y solo la frase es inventada; pedir confirmación a Diego |
| Construir de más y contar de menos (muchas funcionalidades, poca historia) | Alcance congelado en [[Visión de producto]]; lo que no responde a las tres preguntas no entra |
| Correos a direcciones reales del dataset | Con servidor real, todo va a `MAIL_REDIRECT_TO`; sin eso el backend no arranca |

## Números de hoy

| Indicador | Valor |
|---|---|
| Pruebas unitarias en Go | 50 funciones, todas en verde |
| `make smoke` | 24/24 verificaciones en 10 escenarios (el 10 es "explicar antes de disputar") |
| JMeter (5 usuarios, 60 s, DeepSeek) | 0 errores · chat p50 970 ms / p95 1,3 s · fuera de alcance p50 12 ms |
| Comparación de modelos (`llmcheck`) | Flash: 100% monto, 93% fecha, 100% comercio, 1,0 s, USD 0,0017 por 16 mensajes |
| Costo de DeepSeek por mensaje | ~USD 0,0001 |
| Calidad de datos (`make profile`) | 23,5 M filas · 0 duplicados · 0 llegadas tardías · 0 líneas ilegibles · `amount_usd` vacío en 57% y con ±2% de ruido |
| ETL (`make etl`) | 23,5 M filas → silver en ~58 min (segunda corrida: 3 s, no reprocesa) · 0 en cuarentena · 33 hallazgos contados en el linaje · `amount_usd` recalculado (solo 607 sin tasa, 0,014%) · 8 pruebas verdes (`make test-etl`) |
| Corrida local del líder (29 sep) | `make etl`: 14 de 15 tablas; `digital_events` se detuvo por falta de disco (el loader no la usa) · `make seed`: 150.000 clientes, 400.000 productos, 4.425.008 transacciones, 1.200 agentes, 13.164 tasas · smoke 22/22 contra el dataset completo |

> [!note] Cómo mantener esta página
> Cada vez que se termina algo: mover la fila del semáforo, tachar o agregar en "Qué falta", actualizar
> "Números de hoy" y la fecha de `actualizado`. Lo hace quien hizo el cambio (o su asistente) en el mismo commit.
