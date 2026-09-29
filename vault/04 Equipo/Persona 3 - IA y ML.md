---
tags: [equipo, persona3, ml]
rol: IA / ML, prompts, clasificador, embeddings
---

# Persona 3 — IA y ML

> [!tip] Tu rol en una frase
> Eres quien le da al sistema su **inteligencia medible**: el clasificador que aprende, la búsqueda de políticas
> (RAG) y el LLM real — cada uno comparado contra un baseline y registrado en **MLflow**.

## Qué estamos haciendo (contexto en 1 minuto)

El asistente ya funciona de punta a punta y el **LLM ya es real** (DeepSeek Flash, conectado por el líder el 27
sep). Queda una pieza "de mentira": el **clasificador por palabras clave**. Tu trabajo principal es reemplazarlo
por uno entrenado **sin cambiar su contrato (C2)**, así nada más se rompe, y cuidar la calidad del LLM. Lee
[[Visión general]], [[ml-service (clasificador)]] y [[LLM]].

## Lo que ya tienes a mano

- `ml/service/app.py`: el stub con el contrato C2 exacto (`/classify`, `/embed`, `/health`, `/metrics`).
- `backend/internal/llm/`: la interfaz `Provider`, el simulado `fake.go` y el real `deepseek.go` (prompts
  `deepseek-prompts-v2`), con tests.
- `backend/cmd/llmcheck`: compara proveedores con 16 mensajes etiquetados ES/PT (acierto, latencia, costo). Úsalo
  cada vez que cambies un prompt: `cd backend && go run ./cmd/llmcheck`.
- Tabla `kb_chunks` con `embedding vector(384)` lista en Postgres.
- Datos: la capa **silver** (`data/silver/`, tras `make etl`), no los CSV crudos. Modelo: [[Modelo ER]].

> [!danger] Tu plan original cambió: el dataset NO trae texto de disputas (29 sep)
> El EDA y el perfilado (P2) demostraron que las 171.321 transcripciones salen de **2 plantillas de
> consulta de saldo** (42 textos de cliente distintos, solo español), `detected_intents` tiene **un**
> valor (`consulta_general`) y `contact_reason` son 6 categorías genéricas. **No hay nada que aprender
> de ahí sobre disputas**: la tarea de "calidad de etiquetas" quedó respondida (no sirven) y el
> dataset de entrenamiento se construye con frases `team_generated`.
> - **Entrenamiento:** genera/escribe frases en ES y PT etiquetadas con la taxonomía C6 (ya congelada:
>   "Cobro indebido" → `wrong_amount`). Documenta el protocolo de generación en `docs/ml_labels.md`.
> - **Sin fuga con la evaluación:** tus frases de entrenamiento y los ~200 casos held-out de P4 deben
>   venir de lotes/autores/instrucciones distintos; acuérdalo con P4 antes de generar.
> - Las transcripciones reales solo sirven como ejemplos de `out_of_scope` (consultas de saldo):
>   léelas de `data/silver/call_transcripts/`.
> - El stub por palabras clave clasifica "crédito" como `out_of_scope` (falla con "tarjeta de crédito")
>   y no tiene palabras para "cobro indebido", que ahora es el 20% de los reclamos: tu modelo real
>   debe cubrir ambos.

> [!info] Resultado de la comparación (ya hecha)
> Flash: 100% montos, 93% fechas, 100% comercios, p50 1,0 s, USD 0,0017 por 16 llamadas. Pro: mismo acierto,
> 1,55 s, USD 0,0045. **Flash quedó como principal**, Pro de respaldo. Con el prompt v2 (caché) el p50 bajó a
> ~0,87 s. Detalle en [[LLM]].

## Qué te toca

| Fecha | Tarea | Entregable | Hecho |
|---|---|---|---|
| dom 27 sep | Probar DeepSeek Flash vs Pro con mensajes ES/PT: calidad, latencia, costo | `llmcheck` + ADR 0004 (lo hizo el líder) | ☑ |
| dom 27 – lun 28 sep | ~~Calidad de etiquetas~~ → respondida por P2: las etiquetas del dataset no sirven (ver aviso). Documenta la evidencia y el protocolo de generación | `docs/ml_labels.md` | ◐ |
| lun 28 sep | Taxonomía (C6) con P2 y P4 | ✅ decidida 28 sep: `Fees` → `wrong_amount` (`analysis/mappings/contact_reason_to_flow.csv`) | ✅ |
| lun 28 – mar 29 sep | Corpus `team_generated` ES/PT etiquetado con C6, sin fuga con los casos de P4 (lotes separados); split por lote, no temporal; B0, B1, M1 (TF-IDF), M2 (e5 + LogReg) en MLflow | `ml/data/`, `ml/train.py`, runs | ☐ |
| mar 29 sep | Umbral de confianza (precisión ≥ 0,95 en validación) | valor congelado + justificación | ☐ |
| mié 30 sep | **ml-service real** con el contrato C2 (tests, p95 < 100 ms en CPU). "Laya" es un modelo candidato; **su descarga está pendiente de aprobación** | `ml/service/` | ☐ |
| mié 30 sep – jue 1 oct | RAG: indexar políticas + FAQ en `kb_chunks`, evaluar recall@3 | `ml/rag/` | ☐ |
| jue 1 oct | Prompts: v1 → v2 (caché) ya hecho; ampliar los 16 mensajes de `llmcheck` con casos dev de P4 y, si hace falta, v3 | `backend/cmd/llmcheck`, `deepseek.go` | ◐ |
| vie 2 oct | Comparar Flash vs Pro (y `LLM_COMPOSE=template` vs `ai`) sobre los casos dev de la evaluación | nota para el ADR 0004 | ☐ |
| vie 2 – sáb 3 oct | Análisis de errores por idioma, país, segmento y acento; variabilidad (3 corridas) | `docs/ml_report.md` | ☐ |

## Conceptos clave (en simple)

- **Fuga de información**: que el modelo "vea la respuesta" durante el entrenamiento. Por eso nunca se usan
  campos derivados del mismo texto ni resultados de la atención.
- **Split temporal**: entrenar con el pasado y evaluar con el futuro, como pasaría en la vida real.
- **Umbral de confianza**: por debajo, el sistema **pregunta** en vez de actuar. Es la forma de mostrar "sabe
  cuándo no actuar".
- **Embeddings**: convertir texto en 384 números; textos con el mismo significado quedan cerca, aunque estén en
  otro idioma. Por eso el modelo entrenado en español sirve para portugués.

## Terminado cuando

MLflow compara B0–M2 con métricas comparables, ml-service real pasa sus tests, `make smoke` sigue en verde, la
RAG está evaluada, la versión final del prompt está registrada con su corrida de `llmcheck` y `docs/ml_report.md`
existe.

## Con quién te coordinas

[[Persona 2 - Datos]] (datos y taxonomía) · [[Persona 4 - Evaluación y pitch]] (casos PT de dev, FAQ para la
RAG) · [[Líder]] (integración del LLM en Go).

## Prompts listos para tu asistente

> [!example] Arrancar
> *"Lee AGENTS.md (sección 'P3 — AI / ML'), `ml/service/app.py` y `backend/internal/llm/`. Explícame el contrato C2
> y la interfaz Provider, y propón un plan para reemplazar el stub sin cambiar las respuestas JSON."*

> [!example] Entrenamiento
> *"Lee docs/eda_findings.md (sección de datos) y docs/etl_rules.md. Crea `ml/data/generate_utterances.py`
> que produzca frases team_generated en ES y PT por tipo de disputa de la taxonomía C6 (incluye variantes con
> errores de tipeo, montos en palabras y fechas sin año), etiquetadas y con un manifiesto (lote, plantilla,
> hash) para garantizar que el lote de evaluación de P4 queda separado. Como out_of_scope usa muestras de
> data/silver/call_transcripts. Luego `ml/train.py` con B0, B1, TF-IDF+LogReg y multilingual-e5-small+LogReg
> registrando todo en MLflow (file:ml/mlruns). Usa Poetry, grupo ml."*

> [!example] Calidad del LLM
> *"Lee `backend/internal/llm/deepseek.go` y `backend/cmd/llmcheck/main.go`. Agrega a llmcheck 10 mensajes nuevos ES/PT
> (montos en palabras, fechas sin año, comercios con errores de tipeo) con su resultado esperado. No cambies el
> prompt todavía: corre la comparación y muéstrame qué falla y por qué."*

> [!warning] Recuerda
> `poetry install --with ml` para tus dependencias pesadas. Nunca mandes texto sin enmascarar a un proveedor externo.
> Nunca edites un prompt ya evaluado sin subir `PromptVersion` (`deepseek-prompts-v2` → `v3`) y volver a correr
> `llmcheck`. Nunca pegues la `DEEPSEEK_API_KEY` en el chat de tu asistente.
