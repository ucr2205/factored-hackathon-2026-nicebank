---
tags: [glosario]
---

# Glosario

| Término | En simple |
|---|---|
| **AI-first** | El sistema usa IA donde aporta (entender texto) y reglas donde se necesita certeza (decidir y actuar) |
| **ADR** | Nota corta que registra una decisión técnica y su porqué. Ver [[Decisiones (ADR)]] |
| **acr / LoA** | "Nivel de verificación" del login: 1 = contraseña, 2 = contraseña + código |
| **Auditoría** | Registro de cada paso con la regla que lo justificó (`audit_events`) |
| **Baseline** | El punto de comparación: cómo sería hoy (todo va a un humano) |
| **Caché de prompt** | El proveedor del LLM "recuerda" la parte del mensaje que se repite en cada llamada (las instrucciones) y no la vuelve a procesar: responde más rápido y cobra menos. Por eso el prompt v2 deja las instrucciones idénticas siempre. Ver [[LLM]] |
| **CID (imagen incrustada)** | Imagen que viaja dentro del correo como adjunto *inline*; se ve sin descargar nada de internet. Así va el logo en los correos |
| **Contención** | % de casos que terminan sin pasar a un humano |
| **Contrato** | Acuerdo de formato entre dos piezas. Ver [[Contratos entre módulos]] |
| **DuckDB** | Base de datos de análisis que consulta CSV y Parquet muy rápido, sin servidor |
| **Embedding** | Convertir texto en una lista de números; textos con significado parecido quedan cerca |
| **ETL** | Extraer, transformar y cargar datos. Ver [[ETL y calidad de datos]] |
| **FCR** | *First Contact Resolution*: resuelto en el primer contacto |
| **Fuga de información (leakage)** | Que el modelo vea la respuesta al entrenar; infla los resultados |
| **Gate** | Punto de control del calendario. Ver [[Calendario y gates]] |
| **Goroutine** | Una tarea que Go ejecuta **en paralelo** con otras, muy liviana. La usamos para pedir los datos al LLM mientras el clasificador trabaja. Ver [[Orquestador]] |
| **Handoff** | Pasar el caso a un humano con un resumen estructurado |
| **Held-out** | Casos guardados para evaluar, que nunca se usaron para ajustar |
| **Idempotente** | Hacerlo dos veces da el mismo resultado que una vez |
| **JMeter** | Herramienta para simular muchos usuarios y medir rendimiento |
| **Keycloak** | Servidor de identidad: login, roles, códigos TOTP |
| **Linaje** | Saber de qué archivo y corrida salió cada dato |
| **LLM** | Modelo de lenguaje (como Claude) que se usa por API |
| **Marca de agua (watermark)** | Hasta dónde se procesaron los datos, para procesar solo lo nuevo |
| **MLflow** | Registro de experimentos de ML (parámetros, métricas, modelos) |
| **OIDC / PKCE** | Estándares de login seguro para aplicaciones web |
| **Outbox (bandeja de salida)** | Tabla donde se guarda "hay que mandar este correo" **en la misma operación** que la acción. Un proceso aparte (worker) lo envía después y reintenta si falla. Así nunca sale un correo de algo que no pasó. Ver [[Notificaciones por correo]] |
| **p50 / p95** | Ordenando los tiempos de menor a mayor: **p50** es el del medio (tiempo *típico*, la mitad tardó menos) y **p95** deja por debajo al 95% (tiempo de las respuestas *más lentas*; solo 1 de cada 20 tarda más). Ejemplo: chat con DeepSeek p50 970 ms, p95 1.299 ms |
| **Pandera** | Librería para declarar y validar qué es un dato válido |
| **pgvector** | Extensión de Postgres para buscar por similitud de embeddings |
| **Poetry** | Gestor de dependencias de Python del proyecto (obligatorio) |
| **Prompt injection** | Texto que intenta manipular al asistente ("ignora tus instrucciones…") |
| **RAG** | Buscar primero la información relevante y que el LLM responda solo con ella |
| **RLS** | *Row-Level Security*: la base de datos solo muestra las filas del cliente actual |
| **Seudonimización** | Reemplazar quién es la persona por una referencia sin significado (`cr_…`). El sistema sabe qué datos consultar sin saber el nombre; el nombre real está cifrado y solo se ve cuando hace falta, con auditoría. Ver [[Seguridad]] |
| **Step-up** | Pedir una verificación extra (código) para una acción sensible |
| **TOTP** | Código de 6 dígitos que cambia cada 30 s en una app autenticadora |
| **Traza** | El recorrido de una petición paso a paso, con tiempos (Jaeger) |
| **Wilson (intervalo)** | Forma honesta de dar un rango de error cuando hay pocos casos |

## Logs y API

- **Log estructurado** — Registro en formato JSON (un objeto por línea) en vez de texto libre: se puede filtrar
  por campo (`level`, `route`, `request_id`) y lo entienden las herramientas de logs.
- **Access log** — La línea que deja cada petición HTTP: ruta, estado, duración.
- **`request_id` / `X-Request-ID`** — Identificador único de cada petición. Viaja en la respuesta y en los logs:
  sirve para encontrar exactamente qué pasó cuando alguien reporta un error.
- **OpenAPI / Swagger** — OpenAPI es el formato estándar para describir un API (rutas, datos, errores); Swagger UI
  es la página web que lo muestra y permite probarlo.
