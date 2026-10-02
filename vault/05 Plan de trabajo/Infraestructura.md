---
tags: [plan, infraestructura]
---

# Plan de trabajo — Infraestructura

Prioridad: **P0** imprescindible para entregar · **P1** importante · **P2** si hay tiempo.

## Hecho ✅

- [x] Docker Compose con 9 servicios y *healthchecks* (Postgres+pgvector, Keycloak, ml-service, backend, frontend, Mailpit, OTel, Jaeger, Prometheus)
- [x] Postgres con rol `app_user` sin permisos para saltarse RLS; puerto 5433
- [x] Keycloak: realm importado, tema NiceBank, PKCE, step-up TOTP, recuperación verificada, política de contraseñas
- [x] Mailpit para correos de prueba
- [x] OpenTelemetry → Jaeger (trazas) y Prometheus (métricas)
- [x] Frontend en contenedor (nginx) con cabeceras de seguridad
- [x] Imágenes: backend Go multi-stage (distroless, no-root); ml-service con Poetry
- [x] Sincronización incremental del dataset (`make data`) e inventario (`make inventory`)
- [x] Usuarios de carga `carga01–20` para JMeter
- [x] Repo **privado en GitHub** (`ucr2205/repo-hackhaton`, rama `main`)
- [x] `make env`: crea `.env` desde `.env.example` y genera una `PII_KEY` local (llave de cifrado de nombres y correos)
- [x] `.env.example` con todas las variables de LLM (DeepSeek) y correo, **sin secretos**
- [x] Correo: Mailpit en local y servidor real `mail.netnovation.com:465` (SSL) con redirección obligatoria a `MAIL_REDIRECT_TO`
- [x] Keycloak toma el servidor de correo del `.env` (marcadores `${KC_SMTP_*}` en el realm, sin clave en el repo)
- [x] Recursos de marca generados con `poetry run python scripts/build_brand_assets.py`
- [x] Endurecimiento (commit `2468283`): CSP y cabeceras de seguridad en nginx, colector OTel que borra atributos personales por patrón, comillas SQL seguras al crear el rol en `00_app_role.sh`
- [x] JMeter 5.6.3 instalado en el PC del líder (`C:\Users\uriel\Documents\apache-jmeter-5.6.3`)

## Por hacer

| Prioridad | Tarea | Dueño | Fecha |
|---|---|---|---|
| ✅ | Despliegue preparado por la empresa en `deploy/evon/` (**https://hackathon.evon.solutions**): un dominio con `/` app, `/api/` backend y `/auth/` Keycloak en modo producción, nginx del host con HTTPS, Postgres propio, `MAIL_APP_URL` público, secretos en `.env` del servidor fuera del repo. Alineado con `main` el 2 oct | Empresa + Líder | 2 oct |
| P0 | Entregar al servidor: `pg_dump -Fc --data-only` de la BD `bank` tras `make seed`, la **`PII_KEY`** de ese momento (por un canal seguro, nunca por chat ni repo), `latam-bank-realm.json` y `etl/seeds/demo_customers.csv` | Líder | sáb 3 oct |
| P1 | Decidir con la empresa si se publican `/jaeger/` y `/prometheus/` (con login en nginx, ya preparado) o quedan por túnel SSH | Líder + empresa | sáb 3 oct |
| P1 | Volumen/imagen del modelo real de ml-service (no descargar en cada arranque) | P3 | mié 30 sep |
| P1 | Carga de `kb_chunks` en el arranque o con `make rag` | P3 + Líder | jue 1 oct |
| P1 | `make etl` y `make eval` en el Makefile | P2, P4 | 30 sep / 2 oct |
| P1 | Límites de recursos (CPU/memoria) por servicio en compose | Líder | vie 2 oct |
| P1 | Backups/`pg_dump` antes del demo | Líder | dom 4 oct |
| ~~P2~~ | ~~Dashboard de Grafana~~ → descartado el 1 oct: lo cubren el Resumen del supervisor y Prometheus con reglas y alertas ([[Observabilidad]]) | Líder | — |
| P2 | CI básico (build + tests) en GitHub Actions | Líder | — |
| P0 | Eliminar el cliente `eval-harness`, usuarios de prueba y de carga en el despliegue público | Líder | dom 4 oct |
| P1 | Copiar este vault al repo en `vault/` | Líder | lun 28 sep |

> [!warning] Antes de hacer público el repo
> Revisar que no haya secretos en el historial, quitar `.atl/` (configuración de herramientas de IA) y confirmar
> que `data/`, `.env` y `team/` nunca se subieron. El `.env` real tiene claves de DeepSeek y SMTP y `PII_KEY`:
> nunca debe salir de la máquina.
