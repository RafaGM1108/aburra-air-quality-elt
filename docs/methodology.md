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

`make elt` runs all three. A GitHub Actions cron runs it daily (Phase 4).

## Analyses

There are no notebooks. Exploratory and statistical analyses are scripts in `src/` run with
`make`; they write figures (PNG) and tables (CSV/JSON) to `data/08_reporting/`, and their
conclusions are written in `docs/`.
