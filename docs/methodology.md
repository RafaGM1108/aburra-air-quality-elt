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
5. `make quality`: freshness, row count, station coverage and duplicate-key checks with
   the thresholds in `conf/base.yaml`;
6. `make publish` + `gh release upload`: refresh the `data-latest` release with the
   aggregated marts only (daily and monthly by station, stations), credited to SIATA;
7. fail the run, and open or update a `Daily ELT failed` issue, if any step failed.

The raw history lives only in the Actions cache: it is private to the repository's
workflows and never published (see the terms in `docs/data.md`). GitHub evicts cache
entries unused for 7 days, so a gap of a week without runs would lose the live history;
the historical backfill can be fetched again.

## Daily means, exceedances and ICA

- A daily mean (calendar day, America/Bogota) needs at least 18 valid hours (75%). This
  is a project choice; Res. 2254 de 2017 does not set it. Days below it get no mean,
  exceedance flag or ICA.
- Exceedance: daily mean > 37 µg/m³ (24 h PM2.5 limit, Art. 2 Paragraph 1), compared on
  the unrounded mean.
- ICA (Art. 20–21): the breakpoints of Table 6 are integers with gaps (12 → 13, 37 → 38,
  ...). The daily mean is **truncated to an integer** before the lookup, as the US EPA
  AQI does with its own precision, and the Art. 21 formula is applied and rounded to an
  integer. So 12.9 µg/m³ is ICA 50 "Buena" and 37.5 µg/m³ is ICA 100 "Aceptable" even
  though 37.5 exceeds the 37 µg/m³ limit. Means above 500 µg/m³ have no ICA.
- The dbt unit test `ica_at_every_breakpoint_edge` (`dbt/models/marts/_ica_unit_tests.yml`)
  checks every edge of Table 6 against the real breakpoint seed.

## Analyses

There are no notebooks. Exploratory and statistical analyses are scripts in `src/` run with
`make`; they write figures (PNG) and tables (CSV/JSON) to `data/08_reporting/`, and their
conclusions are written in `docs/`.
