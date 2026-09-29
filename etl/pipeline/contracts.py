"""Pandera contracts generated from each TableSpec.

Types are already enforced upstream (the cast stage quarantines unparseable NOT NULL values and
counts nulled optional ones), so the contract checks what SQL casts cannot express: nullability per
the dictionary, closed value domains after standardization, and numeric ranges. A row failing any
check is quarantined with rule contract.<column>.<check>.
"""

from __future__ import annotations

import pandera.polars as pa

from .specs import TableSpec


def silver_name(spec: TableSpec, col: str) -> str:
    return spec.rename.get(col, col)


def build_schema(spec: TableSpec) -> pa.DataFrameSchema:
    columns: dict[str, pa.Column] = {}
    for col in spec.types:
        if col in spec.drop:
            continue
        checks = []
        if col in spec.isin:
            checks.append(pa.Check.isin(list(spec.isin[col])))
        if col in spec.ranges:
            lo, hi = spec.ranges[col]
            if lo is not None:
                checks.append(pa.Check.ge(lo))
            if hi is not None:
                checks.append(pa.Check.le(hi))
        columns[silver_name(spec, col)] = pa.Column(
            nullable=col not in spec.not_null, checks=checks, required=True
        )
    # strict=False: derived columns (flags, event_date, source_file, _rid) pass through unchecked.
    return pa.DataFrameSchema(columns, strict=False)
