# Aburrá Valley Air Quality ELT — Spec

Kickoff: Monday 2026-10-12, 08:00 (America/Bogota).

**Goal:** production-style ELT pipeline for air quality in the Aburrá Valley (Medellín metro area): ingest station measurements (PM2.5, PM10, O3, etc.), model them with dbt, and serve an analytics dashboard.

**Data** (verify current access method and terms): SIATA open air-quality data; optional weather covariates from Open-Meteo.

**Architecture:** this is a data engineering project, so replace the training/inference pipelines with extract / load / transform. Map data layers: `01_raw` = landing (raw JSON/CSV), `03_primary` = dbt staging, `05_model_input` = dbt marts.

**Stack:** Python extractors (httpx, tenacity for retries), DuckDB, dbt-duckdb (staging / intermediate / marts) with dbt tests and dbt docs, GitHub Actions scheduled workflow (daily cron), Parquet outputs, Streamlit + plotly dashboard.

## Roadmap

- **Phase 0:** setup, repo, issues, Kanban board, CI green.
- **Phase 1:** incremental, idempotent extractor with retries, logging and tests.
- **Phase 2:** load into DuckDB with deduplication; backfill historical data.
- **Phase 3:** dbt models (staging, intermediate, marts: hourly/daily by station, exceedances), dbt tests, dbt docs.
- **Phase 4:** daily orchestration with GitHub Actions; publish the latest aggregated marts (Parquet, no hourly series) as a release asset; data-quality checks that fail the run loudly.
- **Phase 5:** analysis: air quality index categories under the Colombian standard (Resolución 2254 de 2017 — verify thresholds from the official source), worst stations, hourly/weekly/seasonal patterns, critical episodes.
- **Phase 6:** Streamlit dashboard reading the published aggregates; optional simple next-24h PM2.5 forecast.
- **Phase 7:** README with architecture diagram (Mermaid), real findings, screenshots; release v1.0.0.

**Topics:** data-engineering, elt, dbt, duckdb, github-actions, air-quality, medellin, colombia, python, streamlit

## Open checks (before Phase 1)

- [x] SIATA: current access method (API / downloads), update frequency, terms of use.
  Done 2026-10-10, see `docs/data.md`. Live = geoportal API, PM2.5 only; old JSON frozen
  since 2024-08; terms unconfirmed. SIATA will not grant access (2026-10-18, #4):
  publish aggregates only.
- [x] Resolución 2254 de 2017: official thresholds and AQI breakpoints. Done 2026-10-10
  from the MinAmbiente PDF, see `docs/data.md`.
