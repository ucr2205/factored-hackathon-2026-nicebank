# Despliegue de NiceBank en el servidor EVON

Todo lo específico del servidor vive en `deploy/evon/`. El entorno local del desarrollador (`docker-compose.yml` de la raíz, `make up`) sigue igual.

| Archivo | Para qué |
|---|---|
| `docker-compose.nicebank.yaml` | Copia de los servicios pegados en el compose del servidor |
| `env/*.env.example` | Plantillas de secretos (postgres, backend, keycloak) |
| `nginx-hackathon.evon.solutions.conf` | Rutas del nginx del host |
| `adaptar_realm.py` | Cambia las URLs del realm de localhost al dominio |
| `otel-config.yaml` | Collector de trazas apuntando a `nicebank-jaeger` (y span metrics para Prometheus) |
| `prometheus.yml` | Scrape de backend, ml-service y collector (opcional, con `nicebank-prometheus`) |
| `../../infra/postgres/init/03_keycloak_db.sh` | Crea la BD de Keycloak (solo si existe `KEYCLOAK_DB_PASSWORD`, que en local no existe) |

## Qué se agregó al docker-compose.yaml

| Servicio | Contenedor | IP | Puerto host | Uso |
|---|---|---|---|---|
| nicebank-ml | nicebank-ml | .14 | — (interno) | Clasificador y embeddings (Python) |
| nicebank-keycloak | nicebank-keycloak | .15 | 127.0.0.1:8180 | Login OIDC + TOTP (modo producción, BD en Postgres) |
| nicebank-b | nicebank-backend | .16 | 127.0.0.1:8013 | API Go |
| nicebank-f | nicebank-frontend | .17 | 127.0.0.1:3013 | Web (nginx) |
| nicebank-otel | nicebank-otel | .18 | — | Recibe trazas y quita datos personales |
| nicebank-jaeger | nicebank-jaeger | .19 | 127.0.0.1:16686 | Visor de trazas: `/jaeger/` con login en nginx, o por túnel SSH |
| nicebank-prometheus | nicebank-prometheus | .21 | 127.0.0.1:9091 | Métricas, reglas y alertas: `/prometheus/` con login (opcional) |
| nicebank-postgres | nicebank-postgres | .20 | 127.0.0.1:5434 | PostgreSQL 16 + pgvector, exclusivo de NiceBank |

NiceBank tiene su propio Postgres (`pgvector/pgvector:pg16`, la misma imagen del desarrollador) y no toca tu Postgres de producción. Respecto al compose del desarrollador se eliminó Mailpit (se usa el SMTP real, así que `/mail` no aplica en el servidor). Prometheus es opcional: `nicebank-prometheus` usa las mismas reglas y alertas que el entorno local (`infra/prometheus/rules.yml`); el `/metrics` del backend sigue sin ser público. Keycloak pasó de `start-dev` con H2 interno a `start` con BD en Postgres, para que usuarios y sesiones no se pierdan al recrear el contenedor.

**Un solo dominio**: todo se sirve desde `https://hackathon.evon.solutions`, separado por rutas en el nginx del host.

| Ruta | Destino |
|---|---|
| `/` | Frontend (127.0.0.1:3013) |
| `/api/` | Backend (127.0.0.1:8013) |
| `/auth/` | Keycloak (127.0.0.1:8180), configurado con `KC_HTTP_RELATIVE_PATH=/auth` |

Con un solo origen, el navegador nunca hace peticiones entre dominios: no hay CORS que configurar, la política CSP queda en `'self'` y basta un certificado. Los tres puertos escuchan solo en `127.0.0.1`, así que el único acceso desde fuera es el nginx con HTTPS.

## Pasos

### 1. Código

```bash
# El repo (clonado o descomprimido) debe quedar en /opt/servicios-apis/EVON/nicebank
git clone <url-del-repo> /opt/servicios-apis/EVON/nicebank
# El backend corre como uid 65532 (distroless nonroot): los archivos montados deben ser legibles
chmod -R o+rX /opt/servicios-apis/EVON/nicebank/policies /opt/servicios-apis/EVON/nicebank/infra /opt/servicios-apis/EVON/nicebank/deploy
```

### 2. Postgres de NiceBank

No hay que crear nada a mano. La primera vez que arranca `nicebank-postgres`, con el directorio de datos vacío, la imagen ejecuta en orden los scripts de `infra/postgres/init`:

| Script | Qué hace |
|---|---|
| `00_app_role.sh` (repo) | Extensión pgvector y usuario de aplicación sin BYPASSRLS |
| `01_schema.sql` (repo) | Las 15 tablas |
| `02_rls.sh` (repo) | Seguridad por filas, permisos y funciones |
| `03_keycloak_db.sh` | Usuario y BD propia de Keycloak |

Solo crea el directorio de datos:

```bash
mkdir -p /opt/servicios-apis/EVON/nicebank_data/postgres
```

Los datos quedan en `/opt/servicios-apis/EVON/nicebank_data/postgres`, fuera del repo, para que actualizar el código no los toque. Los scripts **solo corren con el directorio vacío**: si una inicialización falla a medias, borra ese directorio antes de reintentar. Simulé la secuencia completa con PostgreSQL 16 y quedan las 15 tablas y la BD `keycloak`.

### 3. Variables de entorno

```bash
cd /opt/servicios-apis/EVON/nicebank
mkdir -p /mnt/EVON_proyectos_env/EVON/nicebank/{postgres,backend,keycloak}
cp deploy/evon/env/postgres.env.example /mnt/EVON_proyectos_env/EVON/nicebank/postgres/.env
cp deploy/evon/env/backend.env.example  /mnt/EVON_proyectos_env/EVON/nicebank/backend/.env
cp deploy/evon/env/keycloak.env.example /mnt/EVON_proyectos_env/EVON/nicebank/keycloak/.env
chmod 600 /mnt/EVON_proyectos_env/EVON/nicebank/*/.env
```

Reemplaza todos los `CAMBIAR`. Las contraseñas de `nicebank_app` y `keycloak` deben coincidir entre `postgres/.env` y los otros dos archivos. Solo se aplican al crear la BD; si las cambias después, hay que hacerlo también con `ALTER ROLE`. El valor más delicado es **`PII_KEY`**: los nombres y correos de los clientes se guardan cifrados con ella, así que debe ser exactamente la clave usada al cargar los datos (paso 5). Si generas los datos tú, créala con `openssl rand -base64 32`.

### 4. Realm de Keycloak (antes del primer arranque)

```bash
python3 deploy/evon/adaptar_realm.py /opt/servicios-apis/EVON/nicebank/infra/keycloak/latam-bank-realm.json \
    --front https://hackathon.evon.solutions --sin-pruebas
```

Esto cambia las URLs de redirección del cliente `web` de localhost a tu dominio. `--sin-pruebas` quita el cliente `eval-harness` y los usuarios de carga; omítelo si el desarrollador necesita correr `make smoke` o `make eval` contra el servidor. Keycloak importa el realm **solo la primera vez**; después, los cambios se hacen desde la consola de administración.

### 5. Carga de datos

Las tablas quedan vacías: los datos vienen de un dataset de ~5 GB en S3 que pasa por un ETL. Calcula varios GB de disco (150 mil clientes, 400 mil productos, 4.4 millones de transacciones). Hay dos caminos.

**A (recomendado): el paquete de carga.** El desarrollador corre `make db-bundle` y te entrega
`nicebank-db-bundle-<fecha>.zip` (~290 MB): trae el script `load_db.py` (Poetry + loguru), el SQL de las tablas y
la seguridad, un CSV por tabla y el realm del mismo momento. Crea el rol de la aplicación y las tablas si faltan,
verifica cada archivo (filas y SHA-256) y la `PII_KEY`, y carga todo en una sola transacción (unos 3 minutos). Se
configura con variables de entorno; la guía está en el `README.md` del zip (y en `deploy/dbload/`). Con el
contenedor ya inicializado, basta con: `DB_HOST=127.0.0.1 DB_PORT=5434 DB_NAME=nicebank DB_ADMIN_USER=nicebank_admin`
(más contraseñas, `APP_DB_USER=nicebank_app` y la `PII_KEY` en su `.env`) y `poetry run python load_db.py`.

**A2: un volcado de Postgres.** En su máquina, después de `make seed`:

```bash
pg_dump -Fc --data-only -h localhost -p 5433 -U bank_admin bank > nicebank_datos.dump
```

Si recibes el realm del desarrollador, vuelve a ejecutar `adaptar_realm.py` sobre él. Junto con el dump debe darte su `PII_KEY` y su `infra/keycloak/latam-bank-realm.json` + `etl/seeds/demo_customers.csv` del mismo momento: el realm lleva el `customer_ref` de cada usuario demo, que tiene que coincidir con los datos. En el servidor:

```bash
docker compose up -d nicebank-postgres      # primero solo la BD, para que se inicialice
docker exec -i nicebank-postgres pg_restore --data-only --disable-triggers -U nicebank_admin -d nicebank < nicebank_datos.dump
```

**B: correr el loader contra el servidor** desde una máquina con el dataset y el ETL ya ejecutado (`make data && make etl`). El puerto solo escucha en localhost del servidor, así que se usa un túnel SSH:

```bash
ssh -N -L 5434:127.0.0.1:5434 usuario@servidor &   # en otra terminal
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5434 POSTGRES_DB=nicebank \
POSTGRES_USER=nicebank_admin POSTGRES_PASSWORD='...' PII_KEY='...' make seed
```

El loader puede reescribir el realm y `demo_customers.csv`; si lo hace, copia esos dos archivos al servidor y vuelve a ejecutar `adaptar_realm.py` (paso 4) antes del paso 6.

### 6. Construir y levantar

```bash
cd <directorio del docker-compose.yaml>
docker compose up -d --build nicebank-postgres nicebank-ml nicebank-keycloak nicebank-jaeger nicebank-otel nicebank-b nicebank-f
docker compose logs -f nicebank-keycloak nicebank-b
```

La imagen de `nicebank-ml` descarga PyTorch CPU y el modelo e5 desde Hugging Face durante la build (varios minutos, necesita internet). Keycloak tarda alrededor de un minuto en el primer arranque porque compila su configuración y crea sus tablas.

### 7. Nginx del host

Pega el contenido de `deploy/evon/nginx-hackathon.evon.solutions.conf` **dentro** del bloque `server` del puerto 443 que ya creaste para `hackathon.evon.solutions`. Antes de recargar, cambia la IP de ejemplo `203.0.113.10` por la tuya o la de tu VPN:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Qué hace ese bloque:

- **Reparte las rutas** entre frontend, backend y Keycloak.
- **Envía las cabeceras `X-Forwarded-*`.** Keycloak las necesita para generar URLs `https`; sin ellas el login falla.
- **Agranda los buffers de cabeceras.** Los tokens de Keycloak son grandes, y sin esto aparece el error 502 "upstream sent too big header".
- **Protege la administración.** Bloquea la consola de admin y el realm `master` (`/auth/admin`, `/auth/realms/master`) salvo para tu IP, y redirige `/auth/` a la app en lugar de a la consola.
- **Solo pasa `/api/` al backend,** así que `/metrics` no queda público.

Validé la sintaxis con `nginx -t`.

`TRUSTED_PROXIES=192.168.100.1/32` en el compose corresponde al gateway de la red `red`, que es por donde llega el tráfico del nginx del host a los contenedores.

### 7b. Herramientas del equipo (opcional)

El líder pidió ver Jaeger y Prometheus desde la URL pública: `https://hackathon.evon.solutions/jaeger/` y
`/prometheus/`. Como no tienen login propio, nginx lo pide (bloques ya incluidos en el `.conf`):

```bash
sudo apt-get install -y apache2-utils                         # si no está htpasswd
sudo htpasswd -c /etc/nginx/nicebank-tools.htpasswd equipo   # pide la contraseña
mkdir -p /opt/servicios-apis/EVON/nicebank_data/prometheus && chown 65534:65534 /opt/servicios-apis/EVON/nicebank_data/prometheus
docker compose up -d nicebank-prometheus nicebank-jaeger nicebank-otel
sudo nginx -t && sudo systemctl reload nginx
```

Si prefieres no publicarlas, borra los dos bloques `location /jaeger/` y `/prometheus/` del `.conf`: Jaeger sigue por
túnel SSH. Sin `nicebank-prometheus`, la pestaña *Monitor* de Jaeger queda vacía (lo demás funciona).

**Código 2FA en ventana:** la app muestra la página de código de Keycloak dentro de un diálogo (iframe). En este
servidor Keycloak está en el mismo dominio (`/auth`), así que el realm ya lo permite (`frame-ancestors 'self'`) y no
hace falta cambiar nada.

### 8. Verificación

```bash
curl -s http://127.0.0.1:8013/api/health
curl -s http://127.0.0.1:8013/api/ready     # comprueba BD y ml-service
curl -s https://hackathon.evon.solutions/api/health
curl -s https://hackathon.evon.solutions/auth/realms/latam-bank/.well-known/openid-configuration | grep -o '"issuer":"[^"]*"'
```

El `issuer` debe ser exactamente `https://hackathon.evon.solutions/auth/realms/latam-bank`. Si sale con `http` o sin `/auth`, revisa las cabeceras del nginx.

Si publicaste las herramientas: `curl -s -o /dev/null -w '%{http_code}
' https://hackathon.evon.solutions/prometheus/`
debe dar `401` (pide login) y, con `-u equipo:<contraseña>`, `302` o `200`.

Después abre `https://hackathon.evon.solutions` e inicia sesión con `cliente01` / `Test-Only-cliente01`. Los usuarios de agente son `agente01` y `agente02`, y el supervisor es `supervisor01`, con el mismo patrón de contraseña. Bloquear una tarjeta pide un código TOTP; `scripts/smoke_chat.py` muestra cómo calcularlo.

## Avisos

Los usuarios demo tienen contraseñas y semillas TOTP públicas en el repositorio. Es aceptable para una demo de hackathon, pero no para datos reales. Si la demo es pública, cambia sus contraseñas o restringe el acceso.

Todos los correos van a `MAIL_REDIRECT_TO` mientras `MAIL_ALLOW_REAL_RECIPIENTS=false`. Mantenlo así, porque los datos demo tienen direcciones de apariencia real.

Si algún día cambias el dominio, hay que cambiarlo en el compose (Keycloak, backend y args del frontend), reconstruir el frontend (Vite incrusta las URLs en el bundle y en la CSP) y actualizar las URLs del cliente `web` en la consola de Keycloak.

