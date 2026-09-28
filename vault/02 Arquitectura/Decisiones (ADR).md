---
tags: [arquitectura, decisiones]
---

# Decisiones (ADR)

Un **ADR** (*Architecture Decision Record*) es una nota corta que explica una decisión importante: qué
decidimos, por qué y qué consecuencias tiene. Los originales están en `docs/adr/` del repo. Para registrar una
nueva decisión usa la plantilla [[Decisión]].

| # | Decisión | Por qué | Consecuencia |
|---|---|---|---|
| 0001 | **Un solo agente conversacional supervisado**, no multiagente | El jurado premia control, reproducibilidad y auditoría; multiagente no da puntos | OpenClaw/Hermes solo para trabajo interno del equipo |
| 0002 | **Montos de política en USD** con la tasa del día de la transacción | La misma regla vale en MX, CO y AR (el peso argentino se mueve mucho) | Depende de la tabla de tasas; los huecos se reportan |
| 0003 | **Identidad seudonimizada**: referencia opaca en el token, nombres cifrados, identidad solo tras tomar el caso | El código sabe qué filas consultar sin saber quién es la persona (idea de odonto-back) | Cambiar `PII_KEY` exige `make seed`; ver [[Seguridad]] |
| 0004 | **LLM: DeepSeek V4.1 Flash**, V4 Pro de respaldo, simulado como último recurso | Llaves disponibles; en 16 mensajes Flash acertó igual que Pro (100% monto, 93% fecha, 100% comercio) con 1,0 s vs 1,55 s y menos de la mitad del costo; nunca bloquea un turno | Solo texto enmascarado; prompt v2 estable para la caché y extracción en paralelo; repetir la comparación con los casos held-out. Ver [[LLM]] |
| 0005 | **Correos al cliente con bandeja de salida** (outbox) y worker SMTP; alias `nicebank@evon.solutions` | El correo sale solo si la acción se guardó; reintenta si el servidor falla | Con servidor real todo va a `MAIL_REDIRECT_TO`; Keycloak usa el mismo servidor sin clave en el repo; ver [[Notificaciones por correo]] |

## Otras decisiones tomadas (sin ADR formal aún)

| Decisión | Motivo |
|---|---|
| Clasificador propio + LLM solo cuando duda | Hay que mostrar un componente aprendido vs baseline; menos costo y latencia |
| Observabilidad: OTel → Jaeger + Prometheus, sin Loki | Piden trazas y registros; el dashboard es opcional |
| Repo en inglés; equipo en español | Repo público evaluado |
| Python solo con Poetry | Reproducibilidad (decisión del líder) |
| Commits con opencode, sin líneas de atribución a IA | Flujo del equipo; historial limpio |
| Correos solo con la paleta NiceBank (burgundy y rosa del logo) | Identidad de marca consistente en app, login y correos |
| Consola y supervisión en español claro, lo técnico detrás de un interruptor | Los agentes no son técnicos; los auditores igual ven todo |
| Postgres en el puerto 5433 | El 5432 lo usa un PostgreSQL local del líder |
| Login con tema propio de Keycloak (no formulario en la app) | Mantiene PKCE y step-up |
| Recuperación de contraseña con TOTP verificado | El flujo por defecto de Keycloak **reinicia** el TOTP: riesgo de toma de cuenta |
| Usuarios de carga `carga01–20` sin TOTP | JMeter no puede generar códigos; así nunca pueden bloquear tarjetas |
