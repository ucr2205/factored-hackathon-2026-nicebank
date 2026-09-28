---
tags: [plan, codigo]
---

# Plan de trabajo — Código

Prioridad: **P0** imprescindible · **P1** importante · **P2** si hay tiempo.

## Hecho (27 sep) ✅

- [x] Proveedor LLM real **DeepSeek** detrás de `llm.Provider`: enmascarado, JSON validado, Flash → Pro → simulado
- [x] `cost_usd` real por turno (tokens × precio pico) y métrica `llm_calls_total`
- [x] Comparación de proveedores `go run ./cmd/llmcheck` (16 mensajes) → **Flash elegido**
- [x] Prompt v2 estable para la caché de DeepSeek + extracción **en paralelo** con la clasificación
- [x] Identidad seudonimizada (ADR 0003): `customer_ref`, nombres y correo cifrados, revelar identidad tras tomar el caso
- [x] Correos al cliente (ADR 0005): bandeja de salida, worker con envíos en paralelo, diseño NiceBank ES/PT
- [x] Chat: fechas sin año = última vez que ocurrieron; búsqueda en todo el historial si hay monto o comercio sin
      fecha; "no encontré" dice qué buscó; el año aparece cuando no es el actual
- [x] Endurecimiento de seguridad: enmascarado de documentos/CPF/teléfonos con etiqueta, límite de tamaño de las
      respuestas de ml-service, limpieza de trazas, cabeceras de seguridad (commit `2468283`)
- [x] Consola del agente en español claro; nombres de colas legibles; "Ver detalle técnico"
- [x] Barra de navegación con íconos, "Casos", menú de cuenta; supervisión explicada
- [x] Marca NiceBank en app, login y correos (`scripts/build_brand_assets.py`)
- [x] Cola de casos con prioridad (insignias de marca), tiempo de espera y orden por urgencia y antigüedad
- [x] **Logs estructurados**: una línea por petición, turno y correo, con `request_id`/`trace_id`; recuperación de
      pánicos en JSON; IP real con `TRUSTED_PROXIES`; `LOG_LEVEL`/`LOG_FORMAT`
- [x] **Swagger / OpenAPI 3.1** en `/api/docs`, con una prueba que exige documentar cada ruta

## Backend (Go) — [[Líder]]

| Prioridad | Tarea | Fecha |
|---|---|---|
| P0 | El agente puede **cerrar o resolver** un caso tomado (hoy solo puede tomarlo y ver la identidad) | mié 30 sep |
| P0 | Tests de integración en Go: RLS, sesión expirada, caída de ml-service, verificación fallida | mar 29 sep |
| P1 | Cola ordenada por prioridad y **tiempo de espera** (en curso: backend listo sin commit, falta la pantalla) | lun 28 sep |
| P1 | RAG: responder preguntas de política con `kb_chunks` (búsqueda por similitud) | jue 1 oct |
| P1 | Detector de idioma (hoy lo elige el cliente con el selector) | jue 1 oct |
| P1 | Límite de tasa por usuario en `/api/chat` | vie 2 oct |
| P2 | Mensaje de "sesión por expirar" en el front | vie 2 oct |

## Frontend — [[Líder]]

| Prioridad | Tarea | Fecha |
|---|---|---|
| P1 | Vista **"Mis disputas"** para el cliente (sus casos abiertos y su estado) | jue 1 oct |
| P1 | Logos de Visa/Mastercard en los correos (elegir fuente: theSVG o Flaticon/kit de Mastercard; anotar licencia) | jue 1 oct |
| P1 | Estado vacío y errores más claros en consola y supervisión | jue 1 oct |
| P1 | Accesibilidad: foco, etiquetas ARIA, contraste (WCAG AA) | vie 2 oct |
| P2 | Mostrar el resumen del handoff redactado por el LLM | vie 2 oct |

## Datos — [[Persona 2 - Datos]]

| Prioridad | Tarea | Fecha |
|---|---|---|
| P0 | `analysis/01_profile.py`, `analysis/02_business.py` | lun 28 sep |
| P0 | `etl/pipeline/` (contratos, dedup, cuarentena, linaje, marca de agua, USD) | mié 30 sep |
| P0 | `etl/load_postgres.py` (reemplaza `seed_demo.py`) | mié 30 sep |
| P1 | `analysis/03_business_case.py` | sáb 3 oct |

## ML — [[Persona 3 - IA y ML]]

| Prioridad | Tarea | Fecha |
|---|---|---|
| P0 | `ml/data/build_dataset.py`, `ml/train.py` con MLflow | mar 29 sep |
| P0 | `ml/service/app.py` real (contrato C2); "Laya" es un candidato, pendiente de aprobar su descarga | mié 30 sep |
| P1 | `ml/rag/ingest.py` + evaluación recall@3 | jue 1 oct |
| P1 | Registro de versiones de prompts (`deepseek-prompts-v2` → siguiente) con resultados de `llmcheck` | jue 1 oct |

## Evaluación — [[Persona 4 - Evaluación y pitch]]

| Prioridad | Tarea | Fecha |
|---|---|---|
| P0 **crítico** | `eval/RUBRIC.md`, `eval/cases/*.jsonl` (~200 casos held-out) | jue 1 oct |
| P0 **crítico** | `eval/run_eval.py`, `eval/metrics.py`, `make eval` | vie 2 oct |
| P1 | Juez LLM para tono y fidelidad (con validación humana de 30 casos) | sáb 3 oct |

> [!note] Regla general
> Cada tarea de código termina con: tests o script reproducible, `make smoke` en verde, docs en inglés y commit
> con opencode. Ver [[Cómo trabajar con opencode o Claude Code]].
