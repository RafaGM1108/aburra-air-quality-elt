# Aburrá Valley Air Quality ELT

[![CI](https://github.com/RafaGM1108/aburra-air-quality-elt/actions/workflows/ci.yml/badge.svg)](https://github.com/RafaGM1108/aburra-air-quality-elt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/RafaGM1108/aburra-air-quality-elt/graph/badge.svg)](https://codecov.io/gh/RafaGM1108/aburra-air-quality-elt)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A daily, tested ELT pipeline that turns SIATA air quality measurements for Medellín and
> the Aburrá Valley into clean hourly and daily tables and a public dashboard.

## Overview

Python extractors pull hourly PM2.5 per station from SIATA every day, DuckDB stores it
with deduplication, and dbt models it into hourly/daily marts with exceedances and air
quality index (ICA) categories under Colombia's Resolución 2254 de 2017. A Streamlit
dashboard reads the published data.

## Motivation

The Aburrá Valley's topography traps pollutants, and PM2.5 episodes recur twice a year.
SIATA publishes live readings, but only a short rolling window: this project keeps the
history and makes it easy to answer which stations, hours and seasons are worst.

## Data

- **SIATA** geoportal API: hourly PM2.5 for ~23 official stations (72 h rolling window),
  collected daily. Historical JSON files cover 2023-07-31 → 2024-07-31 for a backfill.
- **Open-Meteo** (optional): hourly weather covariates.

Endpoints, limitations, terms and the Resolución 2254 thresholds are in
[`docs/data.md`](docs/data.md). Data is © SIATA / Área Metropolitana del Valle de Aburrá.

## Approach

1. **Extract**: `httpx` + `tenacity` retries, incremental and idempotent, raw JSON to `data/01_raw`.
2. **Load**: DuckDB raw tables, deduplicated on station and hour.
3. **Transform**: dbt-duckdb staging → intermediate → marts, with dbt tests and docs.
4. **Orchestrate**: GitHub Actions daily cron with data-quality checks that fail loudly.
5. **Serve**: Streamlit + plotly dashboard.

## Results

TODO: results go here **only** after an actual run. Every number and figure must come
from a file in [`data/08_reporting/`](data/08_reporting/).

| Metric | Value | Source |
|--------|-------|--------|
| TODO | TODO | `data/08_reporting/TODO.json` |

## Project structure

```text
├── conf/base.yaml          # Paths and parameters
├── data/                   # Layered data (01_raw … 08_reporting), see data/README.md
├── docs/                   # MkDocs Material site
├── src/aburra_air/
│   ├── data/               # Extractors and loaders
│   ├── pipelines/          # extract_pipeline, load_pipeline, transform_pipeline
│   ├── app/                # Streamlit dashboard
│   └── utils/              # Config loader and logging
├── tests/                  # Mirrors src/
└── Makefile                # Common commands (make help)
```

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and `make`.

```bash
git clone https://github.com/RafaGM1108/aburra-air-quality-elt.git
cd aburra-air-quality-elt
make install                 # dependencies + pre-commit hooks
cp .env.example .env         # then fill in secrets, if any
make lint typecheck test     # check everything works
```

| Command | What it does |
|---------|--------------|
| `make extract` / `make load` / `make transform` | Run one ELT step |
| `make elt` | Run the full pipeline |
| `make app` | Streamlit on http://localhost:8501 |
| `make coverage` | Tests with an HTML coverage report |
| `make docs` | Serve the documentation locally |

## Roadmap

| Phase | Milestone | Status |
|-------|-----------|--------|
| 0 | Phase 0 - Setup | 🟨 |
| 1 | Phase 1 - Extract | ⬜ |
| 2 | Phase 2 - Load and backfill | ⬜ |
| 3 | Phase 3 - dbt models | ⬜ |
| 4 | Phase 4 - Orchestration | ⬜ |
| 5 | Phase 5 - Analysis | ⬜ |
| 6 | Phase 6 - Dashboard | ⬜ |
| 7 | Phase 7 - Docs and v1.0.0 | ⬜ |

Work is tracked on the [Kanban board](https://github.com/users/RafaGM1108/projects/12): one
milestone per phase, small issues, and a PR per issue.

## Tech stack

Python 3.12 · uv · httpx · tenacity · DuckDB · dbt-duckdb · Parquet · Streamlit · plotly ·
pytest · ruff · mypy · bandit · pre-commit · GitHub Actions · MkDocs Material

## Author

**Rafael E. Garcia**

- GitHub: [@RafaGM1108](https://github.com/RafaGM1108)
- LinkedIn: [linkedin.com/in/rafaelgarcia11](https://www.linkedin.com/in/rafaelgarcia11)

Licensed under the [MIT License](LICENSE).
