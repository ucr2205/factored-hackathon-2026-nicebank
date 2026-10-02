# Cambios para el despliegue en el servidor EVON

Resumen para el desarrollador. Ningún cambio altera el entorno local (`make up`).

**Nuevo**
- `deploy/evon/`: compose de los servicios del servidor, plantillas `.env`, configuración nginx, collector OTel, script del realm y guía (`README.md`).
- `infra/postgres/init/03_keycloak_db.sh`: crea la BD de Keycloak en el Postgres de NiceBank. Solo actúa si existe `KEYCLOAK_DB_PASSWORD`; en local imprime un aviso y no hace nada.

**Modificado**
- `README.md`: sección "Server deployment (EVON)" y `deploy/` en el layout.

**Actualizado el 2 oct (alineado con `main`)**
- El frontend recibe `VITE_TOOLS_URL` (antes `VITE_JAEGER_URL`) y el backend `PUBLIC_URL`.
- `otel-config.yaml` igual al de `infra/otel`: conserva la IP del cliente (decisión del equipo) y genera span metrics.
- Opcional: `nicebank-prometheus` y las rutas `/jaeger/` y `/prometheus/` en nginx con usuario y contraseña (`auth_basic`).
- El código 2FA ahora se pide en una ventana dentro de la app; con Keycloak en el mismo dominio no requiere cambios.

**Sin tocar (a propósito)**
- `infra/keycloak/latam-bank-realm.json` sigue con URLs `localhost`. En el servidor se adapta con `deploy/evon/adaptar_realm.py` antes del primer arranque. Si vuelves a generar el realm con `make seed`, el servidor necesita el archivo nuevo más ese script.
- Código de backend, frontend y ml-service: todo se configura por variables de entorno y args de build.

**Cómo queda el servidor**
- Un solo dominio, `https://hackathon.evon.solutions`: `/` frontend, `/api/` backend, `/auth/` Keycloak (`KC_HTTP_RELATIVE_PATH=/auth`). Mismo origen: sin CORS, CSP `'self'`.
- Keycloak en modo `start` (producción) con BD en Postgres, en lugar de `start-dev` con H2.
- Postgres propio: `pgvector/pgvector:pg16`, inicializado con los scripts de `infra/postgres/init`.
- Sin Mailpit (SMTP real con `MAIL_REDIRECT_TO`) ni Prometheus.
- Puertos solo en 127.0.0.1; la consola de admin de Keycloak está restringida por IP en nginx.

**Lo que se necesita del desarrollador**
- Un volcado de datos: `pg_dump -Fc --data-only` de la BD `bank` ya cargada con `make seed`.
- La `PII_KEY` con la que se cargó ese volcado.
- El `latam-bank-realm.json` y `etl/seeds/demo_customers.csv` de ese mismo momento, si cambiaron respecto a este repo.
