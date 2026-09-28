---
tags: [modulo, ml]
estado: provisional (palabras clave)
dueño: Persona 3
---

# ml-service (clasificador)

> [!tip] En simple
> Un pequeño servicio en Python (FastAPI) que responde **"¿qué tipo de disputa es este mensaje?"** con una
> etiqueta y **qué tan seguro está** (confianza de 0 a 1). Si la confianza es baja, el sistema pregunta en vez de
> adivinar. También expone `/embed`, que convierte texto en números para buscar por significado (RAG).

## El contrato (C2) — no cambiar sin avisar

```text
POST /classify  {"text": "...", "lang": "es|pt"}
  → {"label": "duplicate_charge", "confidence": 0.9, "abstain": false, "model_version": "..."}
POST /embed     {"texts": ["..."], "kind": "query|passage"}
  → {"vectors": [ [384 números por texto] ], "model": "..."}
GET  /health  ·  GET /metrics
```

## Hoy vs objetivo

| | Hoy (stub) | Objetivo |
|---|---|---|
| Método | Palabras clave en ES y PT | Embeddings `multilingual-e5-small` + regresión logística |
| `/embed` | Vectores falsos deterministas | Embeddings reales de 384 dimensiones |
| Evidencia | — | Runs en **MLflow**: B0 (mayoría) · B1 (palabras clave) · M1 (TF-IDF) · M2 (embeddings) |

> [!note] Candidato en evaluación (27 sep)
> "Laya" es un modelo candidato para el clasificador real; **su descarga está pendiente de aprobación**. Mientras
> tanto sigue el stub de palabras clave, y el plan de MLflow (B0–M2) no cambia. La supervisión lo muestra como
> "Palabras clave (provisional)".

> [!question] ¿Por qué embeddings multilingües?
> No hay datos en portugués. Un modelo multilingüe entiende que *"cobraram duas vezes"* y *"me cobraron dos
> veces"* significan lo mismo, así que lo entrenado en español sirve para portugués. Medirlo es un hallazgo para
> las slides.

## Cuidado con la fuga de información

Entrada = `customer_text` **enmascarado**. **Nunca** usar `detected_intents`, `detected_keywords`,
`main_topics` ni `mentioned_entities` como entrada (salen del mismo texto). Separación temporal: entrenamiento
≤ dic 2025 · validación ene–mar 2026 · test abr–jun 2026.

## Cómo probarlo

```bash
docker compose up -d --build ml-service
curl -s localhost:8000/health
make smoke          # el backend lo llama en cada turno
```

Archivos: `ml/service/app.py`, `ml/service/pyproject.toml` (Poetry), `ml/service/Dockerfile`.
Guía de trabajo: [[Persona 3 - IA y ML]].
