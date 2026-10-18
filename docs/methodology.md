# Methodology

## Data layers

`01_raw` (landing JSON) → DuckDB raw tables → dbt `03_primary` (staging) →
`02_intermediate` (intermediate) → `05_model_input` (marts, Parquet) → `08_reporting`.
Raw data is immutable. See `data/README.md`.

## Pipelines

| Pipeline | Command | Reads | Writes |
|----------|---------|-------|--------|
| Extract | `make extract` | SIATA / Open-Meteo APIs | `01_raw` |
| Load | `make load` | `01_raw` | DuckDB raw tables (deduplicated) |
| Transform | `make transform` | DuckDB raw tables | dbt staging, intermediate and marts |

`make elt` runs all three.

## Orchestration

`.github/workflows/elt.yml` runs the ELT every day at 20:17 America/Bogota (the 72 h
series lags about 7 h behind real time) and on demand (`workflow_dispatch`):

1. restore `data/01_raw/siata` from the Actions cache (latest `raw-siata-*` entry);
2. `make extract`: today's run folder, plus the historical file the first time;
3. save `data/01_raw/siata` to a new cache entry, even if some stations failed;
4. `make load transform`: rebuild DuckDB and the marts from all landings;
5. fail the run, and open or update a `Daily ELT failed` issue, if any step failed.

The raw history lives only in the Actions cache: it is private to the repository's
workflows and never published (see the terms in `docs/data.md`). GitHub evicts cache
entries unused for 7 days, so a gap of a week without runs would lose the live history;
the historical backfill can be fetched again.

## Analyses

There are no notebooks. Exploratory and statistical analyses are scripts in `src/` run with
`make`; they write figures (PNG) and tables (CSV/JSON) to `data/08_reporting/`, and their
conclusions are written in `docs/`.
