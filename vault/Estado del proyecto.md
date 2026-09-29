---
tags: [estado, resumen, seguimiento]
actualizado: 2026-09-29
---

# Estado del proyecto

> [!tip] Para qué sirve esta página
> Es la foto del proyecto **hoy**: qué ya funciona, qué falta, qué nos preocupa y qué decisiones esperan al
> líder. Se actualiza **cada vez que cambia algo** en el código, la infraestructura o el plan. Si algo aquí no
> coincide con lo que ves en el repo, el repo manda y esta página se corrige.

**Hoy:** martes 29 sep 2026 (día 4 de 10) · **Gate 1:** lun 28 sep, el EDA recomendó confirmar el flujo ·
**Siguiente:** Gate 2, miércoles 30 sep ·
**Congelamiento:** domingo 4 oct 20:00 · **Entrega:** lunes 5 oct. Ver [[Calendario y gates]].

## Semáforo por área

| Área | Estado | En una línea | Más detalle |
|---|---|---|---|
| Chat del cliente y orquestador | ✅ Listo | Entiende, decide con reglas, actúa con confirmación, verifica y escala | [[Orquestador]] |
| Inteligencia artificial (LLM) | ✅ Listo | DeepSeek Flash real, Pro de respaldo y reglas como último recurso | [[LLM]] |
| Identidad y seguridad | ✅ Listo | Referencia opaca, nombres cifrados, TOTP, RLS, endurecimiento | [[Seguridad]] |
| Correos al cliente | ✅ Listo | 3 correos con diseño NiceBank + recuperación de contraseña, mismo servidor | [[Notificaciones por correo]] |
| Consola del agente y supervisión | ✅ Listo | En español claro; prioridad y tiempo de espera en la cola | [[Frontend]] |
| Logs, trazas y métricas | ✅ Listo | Un log por petición con `request_id` y `trace_id`; Jaeger y Prometheus | [[Observabilidad]] |
| Documentación del API | ✅ Listo | Swagger UI en http://localhost:8081/api/docs | [[Backend (Go)]] |
| Pruebas | 🟡 Parcial | 32 pruebas en Go, smoke 22/22, JMeter sin errores; faltan pruebas de integración | [[Estrategia de pruebas]] |
| Clasificador de casos | 🔴 Provisional | Sigue siendo por palabras clave | [[ml-service (clasificador)]] |
| Datos y ETL | ✅ Listo | **Pipeline raw → silver + loader**: el sistema ya carga el dataset completo saneado (150k clientes, 4,4M transacciones); falta solo el caso de negocio del pitch | [[ETL y calidad de datos]] |
| **Evaluación (sistema vs baseline)** | 🔴 **Falta** | Sin arnés ni casos held-out: es entregable obligatorio | [[Evaluación]] |
| Entregables (README, slides, video) | 🔴 Falta | Aún no empiezan | [[Persona 4 - Evaluación y pitch]] |
| Despliegue | 🟡 Pendiente | Lo hace la empresa; falta URL pública y quitar lo de prueba | [[Infraestructura]] |

## Lo que ya funciona

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
2. 🔴 **Clasificador real** que reemplace las palabras clave (baselines, TF-IDF, embeddings; Laya como
   candidato). ⚠️ **Su guía se reconfiguró el 29 sep**: sin texto de disputas en el dataset, el corpus es
   `team_generated` (ES/PT) con lotes separados de la evaluación; las transcripciones solo dan ejemplos
   fuera de alcance. → [[Persona 3 - IA y ML]]
3. 🟢 **Datos:** ~~reporte de calidad~~, ~~EDA del Gate 1~~, ~~ETL raw → silver~~ y ~~loader a Postgres~~
   (hechos); queda el caso de negocio del pitch (`analysis/03_business_case.py`). → [[Persona 2 - Datos]]
4. 🔴 **Entregables:** README, `docs/architecture.md`, `docs/production_gap.md`, 4–6 slides y video.
5. 🟡 **Producto:** "Mis disputas" para el cliente, cerrar y resolver casos en la consola, correo al resolver.
6. 🟡 **Pruebas de integración en Go:** aislamiento RLS, expiración de sesión y fallas de herramientas.
7. 🟡 **Despliegue:** URL pública (enlaces y logo de los correos), quitar el cliente `eval-harness` y los
   usuarios de prueba, gestor de secretos, apagar Swagger (`DOCS_ENABLED=false`).

## Decisiones que esperan al líder

- [ ] Enviar la **prueba real del correo de recuperación** con `cliente20`.
- [ ] **Logos de tarjeta:** theSVG para las tres marcas (recomendado) o Flaticon con atribución + acuerdo de
  Mastercard.
- [ ] Qué hacer con la línea `Co-Authored-By` en los 11 commits antiguos (dejarlos o reescribir historia).
- [ ] Aprobar la **descarga de Laya** (~300–400 MB) para probarlo como clasificador.
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
| DeepSeek se cae o tarda | Pro de respaldo y reglas locales; el cliente nunca se queda sin respuesta |
| Los datos traen 84–88% de las filas anunciadas | ✅ Explicado en el reporte de calidad: el faltante está repartido parejo en el tiempo, no son datos por llegar |
| No hay ningún cargo duplicado real en los datos | El tipo `duplicate_charge` se demuestra y evalúa con casos `team_generated` (P4) |
| Un reclamo no se puede ligar a su transacción (`affected_product_id` ajeno, montos reclamados al azar) | La transacción se busca con lo que dice el cliente en el chat, como ya hace el backend |
| No hay frases reales de disputa en los datos (las transcripciones son 2 plantillas de saldo, sin portugués) | P3 entrena y P4 evalúa con frases `team_generated` en ES y PT |
| 79.930 clientes comparten su correo con otro cliente (el generador lo arma con inicial + apellido) | Un aviso "a un cliente" llegaría a otras personas: hoy no pasa porque con servidor real todo va a `MAIL_REDIRECT_TO`; hay que anotarlo en la brecha a producción (P4) |
| Correos a direcciones reales del dataset | Con servidor real, todo va a `MAIL_REDIRECT_TO`; sin eso el backend no arranca |

## Números de hoy

| Indicador | Valor |
|---|---|
| Pruebas unitarias en Go | 32 funciones, todas en verde |
| `make smoke` | 22/22 verificaciones en 9 escenarios |
| JMeter (5 usuarios, 60 s, DeepSeek) | 0 errores · chat p50 970 ms / p95 1,3 s · fuera de alcance p50 12 ms |
| Comparación de modelos (`llmcheck`) | Flash: 100% monto, 93% fecha, 100% comercio, 1,0 s, USD 0,0017 por 16 mensajes |
| Costo de DeepSeek por mensaje | ~USD 0,0001 |
| Calidad de datos (`make profile`) | 23,5 M filas · 0 duplicados · 0 llegadas tardías · 0 líneas ilegibles · `amount_usd` vacío en 57% y con ±2% de ruido |
| ETL (`make etl`) | 23,5 M filas → silver en ~58 min (segunda corrida: 3 s, no reprocesa) · 0 en cuarentena · 33 hallazgos contados en el linaje · `amount_usd` recalculado (solo 607 sin tasa, 0,014%) · 8 pruebas verdes (`make test-etl`) |

> [!note] Cómo mantener esta página
> Cada vez que se termina algo: mover la fila del semáforo, tachar o agregar en "Qué falta", actualizar
> "Números de hoy" y la fecha de `actualizado`. Lo hace quien hizo el cambio (o su asistente) en el mismo commit.
