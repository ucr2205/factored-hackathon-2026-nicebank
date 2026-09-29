# Data Freshness and Late-Arrival Policy

How the pipeline (`make etl`) keeps silver — and through the loader, the operational Postgres — up to
date when the organizer delivers new or corrected files. The dataset is delivered as daily-partitioned
CSV files re-synced with `make data`; delivery is batch, so processing is batch: nothing here needs
streaming (per the problem statement, incremental file delivery does not by itself require it).

## Watermark: what "new" means

A raw file is identified by its **path + size + mtime** (`etl_files` in `data/etl_state.duckdb`).
`make etl` processes a file when that triple is unseen: a re-synced partition (same path, new content)
or a brand-new partition becomes pending automatically; everything else is a no-op. Running the
pipeline twice in a row therefore does nothing the second time (verified by `make test-etl`).

## Late arrivals

The dictionary announces late-arriving partitioned data. Two facts of this dataset shape the policy:

1. **`process_date` is a load date with a day cutoff** (06:00 for transactions/events/sends, 08:00 for
   complaints/calls): events in the first hours of a day are filed under the previous `process_date`
   and partition folder. Business dates therefore always come from the event timestamp (`event_date`
   in silver), never from `process_date` or the folder.
2. **A re-delivered record keeps its primary key** with a newer `process_date`. Dedup keeps the newest
   version, so a late correction replaces the stale row instead of duplicating it.

For the two large fact tables (silver partitioned by event month), a pending file triggers a rebuild
of exactly the event months it can touch: the months of its own rows **plus** the months where silver
already holds those primary keys (so a correction that moves an event also removes the stale copy).
Raw files from the day before each affected month are re-read to cover the cutoff. Small tables and
dimensions rebuild whole — they take seconds. There is no organic late data in dataset v1.0.0; the
behavior is proven by the labeled fixture in `etl/tests/` (`make test-etl`).

## Refresh cadence

- **During the hackathon:** re-run `make data` (or refresh the local copy) then `make etl` daily and
  before every evaluation run; `make seed` reloads Postgres from silver afterwards. Each run's
  `etl_runs` row records what changed.
- **Records arriving more than 35 days late** still load correctly (their event month is rebuilt), but
  metrics already reported over that month must be regenerated; the eval harness reads silver, so
  re-running it is enough.
- **Quarantine is re-evaluated per delivery:** a corrected re-delivery of a quarantined row enters
  normally; the quarantined copy stays in its run's parquet as evidence.

## Consumers

Silver is the only source for analysis, training and the Postgres loader. The operational database is
a projection of silver (contract C1) refreshed by `make seed`; it is never edited by hand, so its
freshness equals the last loader run (logged by the loader and visible in `etl_runs`).
