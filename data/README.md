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
