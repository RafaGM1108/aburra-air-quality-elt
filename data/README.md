# Data layers

Data moves through numbered layers. Each layer is produced only from the layers
before it, by code in `src/`, so any layer can be rebuilt from `01_raw`.

| Layer | Contents | Written by |
|-------|----------|------------|
| `01_raw` | Landing zone: API responses exactly as received (JSON), one file per source and run. **Immutable: never edit, overwrite or clean in place.** | Extract pipeline |
| `02_intermediate` | dbt intermediate models (joins, hourly/daily aggregates). | dbt (transform pipeline) |
| `03_primary` | dbt staging: typed, renamed, deduplicated source tables. | dbt (transform pipeline) |
| `05_model_input` | dbt marts: hourly/daily by station, exceedances, ICA (Parquet). | dbt (transform pipeline) |
| `08_reporting` | Metrics (JSON/CSV) and figures (PNG) used in the README and reports. | Analysis code |

## Landing layout

`01_raw/siata/pm25/<YYYY-MM-DD>/stations.json` and `<station code>.json`, one folder per
run date (America/Bogota). Files are written once, atomically, and never changed.

`01_raw/siata/historical/pm25.json`: SIATA's frozen `EntregaData1` PM2.5 file
(2023-07 → 2024-07), landed once by `make extract` and never fetched again.

## DuckDB

`make load` reads every `01_raw` run folder (oldest first) into
`03_primary/aburra_air.duckdb`, schema `raw`:

- `siata_pm25_hourly`: one row per `(station_code, timestamp_hour)`; `timestamp_hour` is
  a `TIMESTAMPTZ` (America/Bogota), `pm25` is `NULL` when SIATA reports it missing.
- `siata_stations`: station metadata from the latest `stations.json`.
- `siata_pm25_historical`: the backfill file, one row per `(station_code, timestamp_hour)`,
  `pm25` `NULL` where SIATA wrote `-9999`, plus SIATA's `quality` flag as text.

Loading is an upsert, so re-running it changes nothing. `make transform` runs dbt
(`dbt/`) on these tables: staging views live in schema `staging` of the same file.
Intermediate and mart models are Parquet files (dbt-duckdb `external`):

- `02_intermediate/int_pm25_hourly.parquet`: live and historical hours on one timeline
  (live wins on overlap), with local date and hour.
- `02_intermediate/int_pm25_daily.parquet`: daily mean by station and valid-hour count.
- `05_model_input/fct_pm25_hourly.parquet`: hourly PM2.5 by station (local use only,
  never published).
- `05_model_input/fct_pm25_daily.parquet`: daily mean by station; `NULL` unless the day
  has at least 18 valid hours (75%, a project choice), with the 24 h exceedance flag
  (> 37 µg/m³) and the ICA (concentration truncated to an integer before the breakpoint
  lookup, Res. 2254 Art. 20–21).
- `05_model_input/agg_pm25_station_monthly.parquet`: valid days, mean and exceedance days
  by station and month.
- `05_model_input/dim_stations.parquet`: stations, including codes seen only in the
  historical data.


## Rules

- `01_raw` is read-only. If raw data is wrong, fix it in `02_intermediate`.
- Paths are set in `conf/base.yaml`. Code never hard-codes them.
- Only small, redistributable samples (`*_sample.*`) and `08_reporting/` are committed.
  Everything else is ignored by git.
- Each source's origin, license and download date is recorded below.

## Sources

| Source | License | Retrieved | Notes |
|--------|---------|-----------|-------|
| SIATA geoportal API (PM2.5, live) | Unconfirmed, see `docs/data.md` | Daily | Undocumented endpoints; 72 h window per station |
| SIATA `EntregaData1` JSON (historical) | Unconfirmed, see `docs/data.md` | 2026-10-10 | Frozen since 2024-08-31; covers 2023-07-31 → 2024-07-31 |
| Open-Meteo (optional) | CC BY 4.0 | TODO | Weather covariates |
