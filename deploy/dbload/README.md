# Carga de la base de datos de NiceBank

Este paquete crea todo lo que necesita la base de datos de NiceBank (rol de la aplicación, tablas, seguridad por
filas y funciones) y la llena con los datos del demo: 150.000 clientes, 400.000 productos, 4,4 millones de
transacciones, tasas de cambio y agentes. Se ejecuta con Poetry y deja un registro con loguru.

| Carpeta / archivo | Qué es |
|---|---|
| `load_db.py` | El script que hace todo |
| `pyproject.toml`, `poetry.lock` | Dependencias (psycopg, loguru, cryptography, python-dotenv) |
| `.env.example` | Variables de conexión: cópialo a `.env` |
| `sql/` | Las mismas tablas, seguridad y funciones que `infra/postgres/init` del repo |
| `data/*.csv` + `data/manifest.json` | Un CSV por tabla, con su número de filas y su huella SHA-256 |
| `keycloak/` | El realm y `demo_customers.csv` del mismo momento que los datos (los usuarios demo deben coincidir) |

## Requisitos

- Python 3.11 o superior y [Poetry](https://python-poetry.org/).
- Acceso al Postgres de NiceBank (`pgvector/pgvector:pg16`; la extensión `vector` debe estar disponible). En el
  servidor EVON el puerto solo escucha en `127.0.0.1:5434`: ejecuta el script en el servidor o con un túnel SSH.
- La **`PII_KEY`** con la que se construyó el paquete (los nombres y correos viajan cifrados con ella). Pídela
  al líder por un canal seguro; no está en el paquete.
- Unos 3 GB libres en el disco del Postgres.

## Pasos

```bash
unzip nicebank-db-bundle-*.zip && cd nicebank-db-bundle
cp .env.example .env && chmod 600 .env      # completa los CAMBIAR
poetry install
poetry run python load_db.py --check-only   # solo verifica los archivos (no se conecta)
poetry run python load_db.py                # crea lo que falte y carga los datos
```

Qué hace, en orden:

1. Se conecta con el usuario dueño de la base (`DB_ADMIN_USER`). Debe ser superusuario o tener `BYPASSRLS`, porque
   las tablas fuerzan la seguridad por filas.
2. Crea la extensión `vector` y el rol de la aplicación (`APP_DB_USER`, sin superusuario ni `BYPASSRLS`) si no existen.
3. Si la base está vacía, crea las tablas, la seguridad por filas, los permisos y las funciones. Si ya existen (por
   ejemplo, las creó el contenedor al arrancar), las deja como están y solo aplica las migraciones pendientes.
4. Verifica cada CSV contra el manifiesto (filas y SHA-256): un archivo incompleto o editado detiene todo.
5. Carga las tablas con `COPY` en **una sola transacción**: si algo falla, la base queda como estaba.
6. Compara las filas cargadas con el manifiesto y comprueba que la `PII_KEY` descifra los nombres.
7. Ejecuta `ANALYZE`.

Los mensajes salen en la consola y en `load_db.log` (junto al script). `LOG_LEVEL=DEBUG` muestra el avance de cada tabla.

## Volver a cargar

Si la base ya tiene clientes, el script se detiene para no duplicar nada. Para reemplazar los datos:

```bash
poetry run python load_db.py --replace
```

`--replace` vacía las tablas de datos **y también** las conversaciones, casos, bloqueos y auditoría que dependen de
ellas (es la carga limpia del demo). No toca usuarios de Keycloak.

## Después de cargar

- El backend debe usar el mismo `APP_DB_USER` / `APP_DB_PASSWORD` en su `DATABASE_URL` y la misma `PII_KEY`.
- Si Keycloak todavía no importó el realm, usa el de `keycloak/latam-bank-realm.json` (en el servidor EVON,
  pásalo antes por `deploy/evon/adaptar_realm.py`): sus usuarios `cliente01`–`cliente20` llevan el `customer_ref`
  que estos datos esperan.

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `cannot connect to Postgres` | Revisa `DB_HOST`/`DB_PORT` (en el servidor: `127.0.0.1:5434` o el túnel SSH) y la contraseña |
| `neither superuser nor BYPASSRLS` | Usa el usuario dueño de la base (`POSTGRES_USER` del contenedor) |
| `SHA-256 does not match` | El zip se copió incompleto: vuelve a descargarlo |
| `already holds … customers` | Ya hay datos: usa `--replace` si quieres reemplazarlos |
| `PII_KEY does not decrypt` | La clave no es la del paquete; no se guardó nada (se deshace la transacción) |
