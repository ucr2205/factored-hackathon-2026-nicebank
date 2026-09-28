---
tags: [modulo, datos, etl]
estado: parcial (inventario + perfilado de calidad + seed de demo)
dueño: Persona 2
---

# ETL y calidad de datos

> [!tip] En simple
> **ETL** = *Extract, Transform, Load*: traer los datos, limpiarlos y cargarlos donde el sistema los usa. El
> jurado evalúa que sea **reproducible** (un comando), con **contratos** (reglas de qué es un dato válido),
> **linaje** (de dónde salió cada fila) y una **política de actualización** (qué pasa con los datos que llegan tarde).

## Capas

```mermaid
flowchart LR
    RAW["raw<br/>CSV exactos de S3"] --> V{"Contratos<br/>Pandera"}
    V -- válido --> SIL["silver<br/>Parquet limpio"]
    V -- inválido --> Q["cuarentena<br/>con motivo"]
    SIL --> PG[("Postgres<br/>contrato C1")]
    SIL --> DK[("DuckDB<br/>análisis y ML")]
```

## Qué existe hoy

| Script | Qué hace |
|---|---|
| `scripts/sync_data.py` (`make data`) | Sincroniza S3 → `data/raw/` (incremental: solo baja lo nuevo) |
| `etl/inventory.py` (`make inventory`) | Genera `docs/data_inventory.md` con archivos, tamaños, filas y alertas |
| `analysis/01_profile.py` (`make profile`) | Perfila la calidad de las 13 tablas → `docs/data_quality_report.md` (~4 min). Lee todo como texto en `data/profile.duckdb` (fuera de Git) y termina con las **reglas para el ETL** |
| `etl/seed_demo.py` (`make seed`) | **Provisional:** carga 20 clientes de demo, sus productos y transacciones, agentes y tasas; crea los usuarios de Keycloak |

## Qué falta (Persona 2)

- [x] **Perfilado** de las 13 tablas → `docs/data_quality_report.md` (28 sep)
- [ ] **EDA de negocio** → `docs/eda_findings.md` (**Gate 1, lun 28 sep 18:00**)
- [ ] **Pipeline** `etl/pipeline/`: contratos Pandera, deduplicación, cuarentena, linaje (`etl_runs`),
      marca de agua, USD con tasa del día
- [ ] Fixture de **llegada tardía** con tests (`make test-etl`)
- [ ] **Loader** a Postgres que reemplace `seed_demo.py`, idempotente
- [ ] `docs/freshness_policy.md`

## Herramientas

DuckDB (consultas rápidas sobre CSV/Parquet), Polars, Pandera (contratos), PyArrow, psycopg. Todo con
**Poetry**: `poetry add <paquete>` y `poetry run python ...`.

Hallazgos: [[Datos del proyecto#Hallazgos que hay que explicar]] y [[Datos del proyecto#Lo que encontró el perfilado]].
Guía: [[Persona 2 - Datos]].

> [!important] Reglas que el perfilado le deja al pipeline
> La fecha de negocio sale del **timestamp del evento** (hay un corte de día a las 06:00/08:00); deduplicar por
> llave aunque hoy no haya duplicados; carga incremental con prueba de llegada tardía; **recalcular `amount_usd`**;
> normalizar "Mexico"/"México" sin perder las compras internacionales; no exigir `registration_branch_id` como
> llave foránea; límites de vacíos por columna, no un 5% global; `affected_product_id` fuera de los cruces;
> coordenadas en (0, 0) → vacías. Detalle en la sección "What this means for the ETL" del informe.
