---
tags: [equipo, persona2, datos]
rol: Datos, ETL y calidad de datos
---

# Persona 2 — Datos, ETL y calidad

> [!tip] Tu rol en una frase
> Eres quien **demuestra con datos por qué este problema importa** y quien deja los datos **limpios, controlados y
> cargados** para que el sistema los use. Sin tu trabajo, el resto construye sobre supuestos.

## Qué estamos haciendo (contexto en 1 minuto)

Un asistente que atiende "no reconozco este cobro" en ES y PT: identifica la transacción, aplica reglas y abre
el caso, bloquea la tarjeta o lo pasa a un humano. Ya funciona de punta a punta con **20 clientes de demo**
cargados por un script provisional. Tú lo reemplazas por una tubería de datos real. Lee [[Visión general]] y
[[El viaje de un mensaje]].

## Lo que ya tienes a mano

- Dataset completo en `data/raw/` (7.671 CSV, 5 GB) · `make data` para re-sincronizar.
- `docs/data_inventory.md` con filas, archivos y alertas · [[Datos del proyecto]] con los hallazgos.
- Esquema destino (contrato C1): `infra/postgres/init/01_schema.sql` · [[Base de datos y RLS]].
- Script de referencia: `etl/seed_demo.py` (cómo leer con DuckDB y cargar a Postgres).

## Qué te toca

| Fecha                | Tarea                                                                   | Entregable                                               | Hecho |
| -------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------- | ----- |
| dom 27 – lun 28 sep  | Perfilado de calidad de las 13 tablas                                   | `analysis/01_profile.py` → `docs/data_quality_report.md` | ✅     |
| **lun 28 sep 18:00** | EDA de negocio + experimento reclamo ↔ transacción (**Gate 1**)         | `analysis/02_business.py` → `docs/eda_findings.md`       | ☐     |
| lun 28 sep           | Taxonomía de tipos de disputa (C6) con P3 y P4                          | `analysis/mappings/contact_reason_to_flow.csv`           | ☐     |
| mar 29 – mié 30 sep  | ETL raw → silver con contratos, deduplicación, cuarentena, linaje y USD | `etl/pipeline/`, `docs/freshness_policy.md`              | ☐     |
| mié 30 sep           | Fixture de llegada tardía + tests                                       | `etl/tests/`, `make test-etl`                            | ☐     |
| mié 30 sep           | Loader a Postgres que reemplaza `seed_demo.py`                          | `etl/load_postgres.py`                                   | ☐     |
| jue 1 – sáb 3 oct    | Números y gráficos para el pitch (supuestos y proyecciones marcados)    | `analysis/03_business_case.py`                           | ☐     |

### Detalle de lo más importante

**Perfilado** — por tabla: filas, tipos, nulos por columna, duplicados exactos y por PK, valores de categóricas,
rangos de fechas, huérfanos contra tablas padre, **evolución de esquema por contenido** (nulos por mes) y
**llegadas tardías** (`process_date` vs fecha del evento). Explica las desviaciones de filas (84–88%, 156%, 439%).

> [!success] Perfilado hecho (lun 28 sep)
> `make profile` (~4 min) regenera `docs/data_quality_report.md`; el detalle queda en `analysis/out/profile/`.
> Lo que encontró está resumido en [[Datos del proyecto#Hallazgos que hay que explicar]], y el informe termina con
> las **9 reglas para el ETL** ("What this means for the ETL").

**EDA para el Gate 1** — ¿qué parte de los contactos son disputas? ¿Cómo les va hoy (resolución al primer
contacto, escalamiento, duración, SLA)? Cortes por país, segmento, canal y mes. **El criterio para confirmar el
flujo:** volumen relevante + dolor medible + datos suficientes. Si no se cumple, se pasa al plan B.

**Experimento clave** — `complaints` no tiene `transaction_id`: busca transacciones del mismo cliente, monto ±1%
y fecha hasta 60 días antes. Reporta % con 0, 1 o más candidatas. Eso define cómo buscamos la transacción.

> [!warning] No uses `affected_product_id` para este cruce
> El perfilado mostró que **nunca** es un producto del cliente que reclama (0 de 44.570). Busca entre las
> tarjetas del propio cliente (`products.customer_id = complaints.customer_id`).

## Terminado cuando

Existen los tres reportes, `make etl` corre dos veces con el mismo resultado (idempotente), el test de llegada
tardía pasa, Postgres queda cargado con el contrato C1 y `make smoke` sigue en verde.

## Con quién te coordinas

- [[Persona 3 - IA y ML]]: taxonomía (C6) y datos para entrenar.
- [[Persona 4 - Evaluación y pitch]]: clientes de demo para los casos de prueba; gráficos para las slides.
- [[Líder]]: cambios al esquema (C1).

## Prompts listos para tu asistente (opencode / Claude Code)

> [!example] Arrancar
> *"Lee AGENTS.md y la sección 'P2 — Data / ETL'. Resume en 5 puntos qué existe en `etl/` y `docs/data_inventory.md`
> y propón el plan para `analysis/01_profile.py` usando DuckDB con `read_csv(..., union_by_name=true)`. Usa Poetry."*

> [!example] Perfilado
> *"Escribe `analysis/01_profile.py` que, para cada tabla de `data/raw/`, calcule filas, nulos por columna, duplicados
> exactos y por PK, huérfanos contra customers/products, nulos por mes para detectar evolución de esquema y atraso de
> process_date. Guarda CSV en `analysis/out/<tabla>/` y genera `docs/data_quality_report.md` en inglés."*

> [!example] Pipeline
> *"Diseña `etl/pipeline/` raw→silver con contratos Pandera (tipos del diccionario, valores permitidos, rangos),
> cuarentena con motivo, dedup por PK conservando el process_date más reciente, tabla etl_runs de linaje y marca de
> agua por archivo. Incluye un fixture de llegada tardía con pytest. No toques `backend/`."*

> [!warning] Recuerda
> Código y documentos del repo **en inglés**. Python **solo con Poetry**. Nunca subir `data/`. Las etiquetas
> (`is_fraud`, `was_resolved`, resolución de reclamos) no son entradas del sistema.
