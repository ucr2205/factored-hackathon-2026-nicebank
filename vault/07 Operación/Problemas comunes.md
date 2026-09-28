---
tags: [operacion, troubleshooting]
---

# Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `make seed` falla con "password authentication failed" en el puerto 5432 | Tienes otro PostgreSQL instalado en Windows | El del proyecto está en **5433**; revisa `POSTGRES_PORT` |
| El login muestra el tema viejo de Keycloak o "Sign in to your account" | Pestaña abierta antes de reiniciar Keycloak | Cerrar la pestaña y entrar de nuevo por http://localhost:5173 (Ctrl+F5) |
| Pantalla en blanco en la app tras instalar librerías | Caché de Vite desactualizado ("Outdated Optimize Dep") | Detener `npm run dev`, borrar `frontend/node_modules/.vite` y volver a arrancar |
| `make smoke` falla en el primer chequeo ("pending_action") | El caso ya existía de una corrida anterior | Correr `make smoke` (que hace `make seed` antes), no solo el script |
| El código TOTP dice "no es válido" | Se venció (dura 30 s) | Generar uno nuevo y usarlo enseguida |
| Cambié `01_schema.sql` y no se aplica | Los scripts de inicio solo corren con volumen nuevo | `docker compose rm -sfv postgres && docker volume rm disputes_pgdata`, levantar y `make seed` |
| Cambié el realm (`latam-bank-realm.json`) y no se aplica | Keycloak solo importa si el realm no existe | `docker compose up -d --force-recreate keycloak` (restaura usuarios y contraseñas) |
| El build del backend falla con "requires go >= 1.26" | Imagen base vieja | El Dockerfile usa `golang:1.26-alpine`; actualizar la local |
| `poetry install` corta con error SSL | Red inestable | Repetir `poetry install` |
| `curl` desde Git Bash rompe acentos en JSON | Codificación de Windows | Usar el script de Python o escapar (`ã`) |
| `make` no existe en Windows | No viene instalado | `winget install ezwinports.make` o copiar el comando del `Makefile` |
| El correo de recuperación no llega | Es un entorno local | Mirar http://localhost:8025 (Mailpit) |
| DeepSeek responde **401** aunque la clave es correcta (en los logs del backend o en `llmcheck`) | La línea del `.env` tiene algo después de la clave (una nota, un comentario, espacios) y se envía como parte de la clave | Dejar la línea solo como `DEEPSEEK_API_KEY=<clave>`, sin nada más; luego `docker compose up -d backend` |
| Un script de Python (smoke, arnés) tarda ~1 s extra en **cada** llamada en Windows | `localhost` primero intenta IPv6 (`::1`) y espera antes de caer a IPv4 | Usar `http://127.0.0.1:<puerto>` en vez de `http://localhost:<puerto>` en los clientes de Python |
| opencode se queda "colgado" cuando otro asistente le pide un commit | La configuración global pide aprobación para cada comando y nadie la da | Correrlo con un `OPENCODE_CONFIG` de solo git (status/diff/log/add/commit, sin push ni edición). Ver [[Cómo trabajar con opencode o Claude Code]] |
| Cambié las variables de correo (`SMTP_*`, `EMAIL_*`, `MAIL_*`) y Keycloak sigue usando Mailpit | Keycloak lee el servidor de correo **solo al importar** el realm | `docker compose up -d --force-recreate keycloak` (también restablece las contraseñas de prueba) |
| `docker compose up` falla con "PII_KEY is missing" | No existe la llave de cifrado en `.env` | `make env` (o `poetry run python scripts/make_env.py`) y luego `make seed` |
| El backend no arranca con un servidor de correo real | Falta `MAIL_REDIRECT_TO` (protección para no escribir a correos del dataset) | Poner tu bandeja de prueba en `MAIL_REDIRECT_TO` |
| "No encontré ningún movimiento…" con una fecha sin año | Antes se leía como fecha futura (ya corregido el 27 sep) | Actualizar a `main`; ahora "23/12" es el último 23 de diciembre |

Para reportar algo nuevo usa la plantilla [[Reporte de bug]].
