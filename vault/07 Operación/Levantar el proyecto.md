---
tags: [operacion, setup]
---

# Levantar el proyecto

## 1. Instalar herramientas (una vez, ~1 hora)

| Herramienta | Para qué | Windows |
|---|---|---|
| Git | Código | `winget install Git.Git` |
| Docker Desktop | Todos los servicios | `winget install Docker.DockerDesktop` |
| Python 3.12/3.13 + **Poetry 2.x** | Datos, ML, scripts | `winget install Python.Python.3.13` → `pipx install poetry` |
| AWS CLI v2 | Descargar el dataset | `winget install Amazon.AWSCLI` |
| Go 1.26+ y Node 22 | Solo si tocas backend/frontend | `winget install GoLang.Go OpenJS.NodeJS.LTS` |
| JMeter 5.6+ (Java 8+) | Solo QA de rendimiento | descarga de jmeter.apache.org |
| Obsidian | Leer este vault | `winget install Obsidian.Obsidian` |

## 2. Primer arranque

```bash
git clone https://github.com/ucr2205/repo-hackhaton.git && cd repo-hackhaton   # repo privado: pide acceso
poetry install                        # P3 además: poetry install --with ml
make env                              # crea .env desde .env.example y genera tu PII_KEY
aws configure --profile factored     # claves por el canal privado del equipo
make data                             # ~5 GB, 15–40 min
docker compose up -d --build          # 9 servicios
make etl                              # limpia raw → silver (contratos, cuarentena, linaje; ~1 h la 1ª vez)
make seed                             # carga TODO el silver a Postgres y cifra identidades con tu PII_KEY
make smoke                            # debe decir "All scenarios passed."
```

> [!note] `make seed` cambió el 29 sep
> Antes cargaba 20 clientes de demo desde los CSV crudos; ahora `etl/load_postgres.py` carga el
> dataset completo (150.000 clientes, 4,4 M transacciones) desde la capa silver, así que necesita
> `make etl` primero. Los 20 usuarios de demo (`cliente01–20`) siguen siendo los mismos.

> [!tip] ¿Ya tienes el dataset descargado (zip del equipo)? No necesitas AWS
> Descomprímelo en cualquier carpeta y enlázala como `data/raw` en vez de `aws configure` + `make data`. En
> Windows, desde la raíz del repo, en **cmd**: `mkdir data` y luego
> `mklink /J data\raw C:\ruta\a\tu\dataset` (no copia nada ni ocupa espacio; `data/` está fuera de Git).
> Todos los scripts (`make inventory`, `make profile`, `make seed`) leen de `data/raw/` igual que con AWS.

Luego abre http://localhost:5173 (desarrollo: `cd frontend && npm install && npm run dev`) o http://localhost:8088.

> [!info] ¿Qué es la `PII_KEY`?
> Es la **llave que cifra los nombres y correos** de los clientes en la base de datos. `make env` genera una al azar
> solo para tu máquina (sin `make`: `poetry run python scripts/make_env.py`). Sin ella el backend no arranca. Si la
> cambias, corre `make seed` para volver a cifrar los datos de demo. **No se comparte ni se sube al repo.**

## 2b. Variables opcionales en tu `.env`

Por defecto todo funciona **sin claves externas**: LLM simulado y correos a Mailpit. Para usar lo real, agrega en
tu `.env` (nunca en `.env.example` ni en el repo; los valores los da el líder por el canal privado):

| Para | Variables | Nota |
|---|---|---|
| LLM real (DeepSeek) | `LLM_PROVIDER=deepseek`, `DEEPSEEK_API_KEY=<clave>` | Opcionales: `LLM_MODEL` (`deepseek-flash`), `LLM_FALLBACK_MODEL` (`deepseek-v4-pro`), `LLM_COMPOSE` (`template`/`ai`) |
| Correo real | `SMTP_HOST`, `SMTP_PORT=465`, `SMTP_SECURITY=ssl`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `MAIL_FROM`, `MAIL_REDIRECT_TO` | `MAIL_REDIRECT_TO` es **obligatoria**: todos los correos van a esa bandeja de prueba. Ver [[Notificaciones por correo]] |

Después de cambiar el `.env`: `docker compose up -d backend` y, si tocaste el correo,
`docker compose up -d --force-recreate keycloak`.

> [!warning] Una variable por línea, sin notas
> Escribe `DEEPSEEK_API_KEY=<clave>` y nada más en esa línea. Una nota o un espacio después de la clave la rompen
> y DeepSeek responde **401**. Ver [[Problemas comunes]].

## 3. Comandos del día a día

| Comando | Qué hace |
|---|---|
| `make help` | Lista todos los comandos |
| `make env` | Crea `.env` (si no existe) y genera la `PII_KEY` (si falta) |
| `make seed` | Reinicia los datos de demo (casos, bloqueos, handoffs) |
| `make smoke` | Reinicia datos y corre los 10 escenarios de punta a punta (incluye identidad, correos y explicar antes de disputar) |
| `make test` | Tests de Go + build del frontend |
| `make load` | Prueba de carga de humo con JMeter (5 usuarios, 60 s) |
| `cd backend && go run ./cmd/llmcheck` | Compara el LLM simulado con DeepSeek en 16 mensajes (necesita `DEEPSEEK_API_KEY` en el entorno) |
| `poetry run python scripts/build_brand_assets.py` | Regenera logos (favicon, app, login, correo) desde `docs/brand/` |
| `docker compose ps` | Estado de los servicios |
| `docker compose logs -f backend` | Ver logs del backend |
| `docker compose up -d --build <servicio>` | Reconstruir un servicio tras cambios |

## 4. URLs

| Servicio | URL |
|---|---|
| **Gateway (entrada única)** | http://localhost:8090 → la app en `/`, el API en `/api` y las herramientas abajo |
| App (dev / contenedor) | http://localhost:5173 · http://localhost:8088 |
| API | http://localhost:8081/api/health |
| **Documentación del API (Swagger)** | http://localhost:8081/api/docs |
| Keycloak | http://localhost:8080 |
| Mailpit (correos) | http://localhost:8090/mail/ |
| Jaeger | http://localhost:8090/jaeger/ |
| Prometheus | http://localhost:8090/prometheus/ |
| Postgres | `localhost:5433`, base `bank` |

> [!important] Jaeger, Prometheus y Mailpit piden usuario y contraseña
> Desde el 2 oct viven bajo el **gateway** (`/jaeger`, `/prometheus`, `/mail`) y piden el *login de
> herramientas*: `TOOLS_USER` y `TOOLS_PASSWORD` en tu `.env`. Si no los tienes, corre `make env` (los crea; la
> contraseña solo queda en tu `.env`) y luego `docker compose up -d gateway`. Para cambiarla:
> `poetry run python scripts/make_env.py --rotate-tools-password`.

### En el servidor público

El servidor real es **https://hackathon.evon.solutions** y lo arma el **nginx del host** con las mismas rutas
(`/`, `/api/`, `/auth/` y, si se decide publicarlas, `/jaeger/` y `/prometheus/` con login). Todo está en
`deploy/evon/` (guía en español: `deploy/evon/README.md`). El gateway Caddy es el espejo local de esas rutas; solo
serviría en un servidor sin proxy propio (`SITE_ADDRESS=<dominio>`, puertos 80/443, HTTPS automático).

## 5. JMeter en Windows sin `make`

Con el sistema levantado y desde la raíz del repo (en el PC del líder JMeter está en
`C:\Users\uriel\Documents\apache-jmeter-5.6.3`):

```powershell
& "C:\Users\uriel\Documents\apache-jmeter-5.6.3\bin\jmeter.bat" -n -t qa/jmeter/nicebank-load.jmx -Jusers=5 -Jramp=10 -Jduration=60 -f -l qa/jmeter/results/results.jtl -e -o qa/jmeter/results/report
```

El reporte queda en `qa/jmeter/results/report/index.html`. Detalle: [[Pruebas de carga con JMeter]].

Si algo falla: [[Problemas comunes]]. Usuarios: [[Credenciales y accesos]].
