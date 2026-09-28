---
tags: [reto, evaluacion]
---

# Cómo nos evalúan

> [!important] Lo primero
> **Que funcione.** Después el jurado mira cinco áreas.

| Área | Qué buscan | Dónde lo mostramos |
|---|---|---|
| Ingeniería de IA | Backend, frontend y despliegue que funcionan | [[Backend (Go)]], [[Frontend]] |
| Ingeniería de datos | Extracción y transformación reproducibles, con contratos y calidad | [[ETL y calidad de datos]] |
| Machine Learning | Selección de modelo, optimización, implementación y **tracking** | [[ml-service (clasificador)]], [[LLM]] |
| Análisis de datos | Calidad de datos e insights útiles | [[Datos del proyecto]] |
| Documentación | Por qué hicimos lo que hicimos, con honestidad | [[Decisiones (ADR)]], README |

## Las métricas que hay que reportar

Siempre **sistema vs baseline**, sobre los **mismos casos held-out**, con **conteos y denominadores**.

| Métrica | En simple |
|---|---|
| Resolución automática segura | De los casos que se podían resolver solos, ¿cuántos resolvimos bien, sin humano y cumpliendo las reglas? |
| Contención | ¿Cuántos casos terminaron sin pasar a un humano? (Sola no prueba que se resolvió bien.) |
| Calidad de escalamiento | ¿Escalamos los que había que escalar, con un resumen útil? ¿Cuántos escalamos de más o de menos? |
| Resultados inseguros | Datos revelados a quien no corresponde, acciones sin permiso o resultados equivocados. **"0 de 50" no es "riesgo cero".** |
| Eficiencia | Latencia p50/p95 y costo por caso intentado y por caso resuelto |

Todo desglosado por **idioma** y **segmento de cliente**. Las mediciones son *offline*: nunca decir "mejora en
producción". Detalle de cómo lo medimos: [[Evaluación]].

## Lo que suma puntos (y lo que no)

- ✅ Profundidad en un solo flujo, reglas fuera del modelo, acciones verificadas, auditoría basada en registros.
- ✅ Honestidad: límites de los datos, del portugués y lo que falta para producción.
- ❌ No suma: más flujos, varios agentes, streaming, dashboard. (Ver [[Decisiones (ADR)]]: agente único supervisado.)
