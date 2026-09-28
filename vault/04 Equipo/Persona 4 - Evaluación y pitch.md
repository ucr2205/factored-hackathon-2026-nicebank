---
tags: [equipo, persona4, evaluacion, pitch]
rol: Políticas, pruebas, evaluación, documentación y pitch
---

# Persona 4 — Evaluación, políticas y pitch

> [!tip] Tu rol en una frase
> Eres quien define **las reglas del banco**, construye **los casos con los que medimos** y **cuenta la historia**
> al jurado. El jurado va a creer lo que tus números digan: por eso tienen que ser honestos.

## Qué estamos haciendo (contexto en 1 minuto)

El asistente ya funciona de punta a punta en ES y PT, con un **LLM real** (DeepSeek Flash) y correos al cliente.
Lo que falta demostrar es **cuánto mejor** es que el proceso actual (todo a humano) y **cuán seguro** es. Eso se
hace con tus casos, tu rúbrica y tu arnés. Lee [[Cómo nos evalúan]], [[Evaluación]] y [[Motor de políticas]].

> [!danger] Tu tarea es la más crítica del proyecto ahora
> Todo lo demás ya existe en alguna versión; **las métricas contra el baseline no**. Sin los ~200 casos held-out y
> el arnés no hay nada que mostrar al jurado en la parte de evaluación. Si te trabas, avisa al líder el mismo día.

## Lo que ya tienes a mano

- `policies/disputes.yaml` **v0** escrito por el líder (tipos, montos, reglas con id). Ahora es tuyo. La pantalla
  de **Supervisión** lo explica en español simple ("qué resuelve solo y qué pasa a una persona"): útil para
  revisarlo y para las slides.
- `scripts/smoke_chat.py`: ya obtiene tokens (con código TOTP de prueba), habla con el chat, confirma, usa
  `?mode=baseline` y lee correos en Mailpit. 9 escenarios en verde. Base del arnés.
- `backend/cmd/llmcheck`: ejemplo de cómo medir acierto, latencia y costo con mensajes etiquetados.
- Resultados de JMeter (humo con DeepSeek, 0 errores): [[Pruebas de carga con JMeter]].
- Contrato del caso (C4) en [[Contratos entre módulos#C4 — Un caso de prueba]].
- Usuarios `cliente01–20` y qué transacciones tienen: [[Credenciales y accesos]].

## Qué te toca

| Fecha | Tarea | Entregable | Hecho |
|---|---|---|---|
| dom 27 – lun 28 sep | Revisar la política v0 (umbrales, plazos, reglas globales); equidad | `policies/disputes.yaml` v0.2 | ☐ |
| dom 27 – lun 28 sep | Rúbrica: resolución segura, resultado inseguro, escalamiento correcto | `eval/RUBRIC.md` | ☐ |
| lun 28 sep | FAQ de 10–15 preguntas en ES y PT (portugués de Brasil) | `knowledge/faq/es`, `knowledge/faq/pt` | ☐ |
| mar 29 sep – jue 1 oct | ~200 casos held-out en formato C4; 20% doble etiquetado; hash del test congelado | `eval/cases/dev.jsonl`, `test.jsonl`, `TEST_HASH` | ☐ |
| jue 1 – **vie 2 oct** | Arnés: sistema vs baseline, métricas con denominadores, Wilson, p50/p95, costo, por idioma y segmento; anotar modelo (`deepseek-flash`) y versión de prompt (`deepseek-prompts-v2`) en cada reporte (**Gate 3**) | `eval/run_eval.py`, `eval/metrics.py`, `eval/reports/` | ☐ |
| vie 2 – sáb 3 oct | Pruebas de carga con JMeter (con el líder): el perfil de humo ya pasó; faltan carga y estrés | informe de rendimiento | ◐ |
| sáb 3 – lun 5 oct | README, arquitectura, brecha a producción, slides (4–6), video (3–5 min) | `docs/`, slides, video | ☐ |

## Cómo armar los casos (en simple)

| Tipo | Cantidad | Ejemplo |
|---|---|---|
| Normal | 60 | "No reconozco un cobro de 385,71 de hoy" → abre caso |
| Ambiguo / no soportado | 40 | "Me cobraram duas vezes, não sei qual" → pregunta · "Quero um empréstimo" → se abstiene |
| Requiere humano | 40 | Monto alto, tarjeta robada, fuera de plazo |
| Adversarial | 60 | Prompt injection, sesión expirada, pedir datos de otro cliente, datos faltantes, falla de herramienta, mezcla de idiomas (10 de cada uno) |

Mitad ES, mitad PT. Los casos en portugués llevan `origin: team_generated`. **30% dev** (se puede usar para
ajustar) y **70% test** (nadie lo mira mientras ajusta).

## Terminado cuando

`disputes.yaml` y la FAQ están revisados, el set de test está congelado con su hash, `make eval` genera el
reporte con denominadores por idioma y segmento, y slides + video están entregados.

## Con quién te coordinas

[[Persona 2 - Datos]] (clientes de demo, gráficos) · [[Persona 3 - IA y ML]] (casos PT de dev, FAQ para la RAG) ·
[[Líder]] (estabilidad del sistema, JMeter, video).

## Prompts listos para tu asistente

> [!example] Arrancar
> *"Lee AGENTS.md (sección 'P4'), `policies/disputes.yaml` y `scripts/smoke_chat.py`. Explícame cada regla de la
> política en lenguaje simple y propón mejoras de equidad y consistencia sin cambiar los rule_id."*

> [!example] Arnés
> *"Crea `eval/run_eval.py` reutilizando token() y call() de scripts/smoke_chat.py: lee eval/cases/*.jsonl (C4),
> ejecuta cada caso en modo sistema y baseline, guarda outcome, acciones verificadas, handoff, latencia y costo.
> Luego `eval/metrics.py` con resolución segura, contención, escalamiento faltante/innecesario, inseguros con
> intervalo de Wilson, p50/p95 y desglose por idioma y segmento. Reporte en eval/reports/<fecha>_<commit>.md. Poetry."*

> [!example] Pitch
> *"Con docs/, eval/reports/ y el vault, propón la estructura de 5 slides y un guion de video de 4 minutos que
> muestre los 3 casos de demo, una traza en Jaeger, la auditoría y las métricas vs baseline."*

> [!warning] Recuerda
> Nunca decir "mejora en producción": son mediciones **offline**. "0 inseguros" siempre con su denominador. Al
> hablar de tiempos, explica p50 (tiempo típico) y p95 (las respuestas más lentas): ver [[08 Glosario|Glosario]].
