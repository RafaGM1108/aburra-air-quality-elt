# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `data/08_reporting/` refreshed from Daily ELT run #5: adds `forecast_baselines.csv`
  and the fixed `monthly_profile.png`; `docs/findings.md` gains a forecast section (#27,
  #57).
- Station ranking ties break on the unrounded mean, then station code, so reruns give the
  same order (#63).
- `monthly_profile.png` labels the x axis with `YYYY-MM` instead of a month index (#57).
- Station id, name and municipality are trimmed in staging; SIATA writes `"Medellín "` (#52).

### Changed

- SIATA will not grant data access or confirm redistribution terms (#4): scope fixed to
  live PM2.5 plus the frozen 2023-07 → 2024-07 history, and only aggregated marts (no
  hourly series, no DuckDB file) will be published.

### Added

- Deploy preparation (#28): `requirements.txt` exported from `uv.lock` (`make
  requirements`, checked in CI), `.streamlit/config.toml`, and `docs/deploy.md` with the
  Streamlit Community Cloud steps. The dashboard re-downloads marts older than 24 h from
  the data release and keeps its copy if that fails.
- Next-day PM2.5 baselines (#27): `make analyze` writes
  `data/08_reporting/forecast_baselines.csv` with MAE, RMSE, bias and skill versus
  persistence of persistence, 7-day mean and same-weekday-last-week forecasts of the
  daily mean, all backtested on the same station-days of the analysis window.
- Dashboard smoke tests (#26) with Streamlit `AppTest` on the fixture marts, in the
  required `test` job: the app loads, every station × period renders without an
  exception, and an empty period shows a message.
- Streamlit + plotly dashboard (#25), `make app`: map of the latest valid day's ICA by
  station, daily means with the 37 µg/m³ line, monthly exceedance days and the
  hour-of-day profile, with a period switch (historical year / live / all). It reads only
  the published aggregates (`aburra_air.data.marts`), downloading any missing mart from
  the `data-latest` release, handles stations without data, and credits SIATA.
- Findings (#24): `docs/findings.md` summarizes the station ranking, seasonal, weekly and
  diurnal patterns and critical episodes, citing only `data/08_reporting/` files from
  the Daily ELT run of 2026-10-18 (fetched with the new `make fetch-reporting`, which
  writes `provenance.json` with each file's upload time and SHA-256).
- Critical episodes (#23): `make analyze` writes `data/08_reporting/episodes.csv` with
  prevención/alerta/emergencia episodes per station from 24 h moving averages and the
  Art. 11/13 48 h / 75% rule; tested on synthetic series (start, end, short spikes, dips,
  escalation, missing hours, open episodes). Skipped where the hourly mart is absent.
- Patterns (#22): new publishable mart `agg_pm25_hour_of_day`, and `make analyze` writes
  `diurnal_profile`, `weekday_profile` and `monthly_profile` (CSV + PNG) to
  `data/08_reporting`, each with valid/possible counts and the pooled coverage printed
  on the figure.
- `make analyze` (#21) writes `data/08_reporting/station_ranking.csv` and `.png`:
  stations ranked by 24 h exceedance days, then mean PM2.5, over the analysis window
  in `conf/base.yaml` (Aug 2023 – Jul 2024, the complete historical year); stations
  with < 75% valid days are listed unranked. The Daily ELT runs it and attaches the
  outputs to the `data-latest` release.
- ICA edge tests (#20): daily means move to `int_pm25_daily`, and a dbt unit test checks
  the ICA and category at every Res. 2254 Table 6 breakpoint edge against the real seed.
  The truncation rule for values between integer breakpoints is documented in
  `docs/methodology.md`.
- Rolling `data-latest` release (#19): the Daily ELT stages `fct_pm25_daily`,
  `agg_pm25_station_monthly` and `dim_stations` with `make publish` (an allowlist that
  refuses any mart with an hourly column) and uploads them with SIATA attribution. Raw
  data, the DuckDB file and hourly series are never published.
- `make quality` (#18), run by the daily ELT after `make transform`: fails the run, listing
  every problem at once, if the latest live hour is too old, the latest run folder is
  short of rows, too few stations reported in the last 24 h, or a mart repeats a key.
  Thresholds in `conf/base.yaml` (`quality:`).
- `Daily ELT` workflow (#17): runs `make extract load transform` every day at 20:17
  America/Bogota and on demand, keeps the raw landings between runs in the Actions cache
  (never published), and opens or updates a `type:bug` issue when a run fails.
- CI runs `make load transform dbt-docs` on the recorded fixtures inside the required
  `test` check, offline, so a broken dbt model or test fails the PR (#16).
- dbt tests and docs (#15): uniqueness of every model's key (generic
  `unique_combination` test), `not_null`, relationships to `dim_stations`, accepted
  values, and plausible ranges (generic `between` test: PM2.5 0–1000 µg/m³, ICA 0–500,
  hours 0–23, coordinates inside the valley). `make dbt-docs` runs `dbt docs generate`.
- dbt intermediate and marts as Parquet (#14): `int_pm25_hourly` (live + historical),
  `fct_pm25_hourly`, `fct_pm25_daily` (18 valid hours minimum, 24 h exceedance of
  37 µg/m³, ICA from a seed of the Res. 2254 breakpoints), `agg_pm25_station_monthly`
  and `dim_stations`.
- dbt-duckdb project in `dbt/` (#13), run by `make transform` (`dbt build`): sources on
  the `raw` tables (live hourly with freshness thresholds, historical, stations) and
  staging views in schema `staging` that set implausible PM2.5 (outside 0–1000 µg/m³) to
  `NULL` while keeping the reported value.
- Historical backfill (#11): `make extract` also lands SIATA's frozen `EntregaData1`
  PM2.5 file once in `01_raw/siata/historical/`, and `make load` upserts it into
  `raw.siata_pm25_historical` (`-9999` as `NULL`, quality flag kept). Bodies that are not
  a non-empty list of stations are never landed. The load now binds whole columns per
  file instead of `executemany`, about 100x faster.
- `make load` upserts every landed SIATA file into DuckDB
  (`data/03_primary/aburra_air.duckdb`): `raw.siata_pm25_hourly` keyed on
  `(station_code, timestamp_hour)` with timestamps in America/Bogota, and
  `raw.siata_stations`. Overlapping runs are deduplicated, newer values win, and a newer
  `null` never erases a value (#10). Tests cover re-loads, overlaps, nulls, rollback of a
  malformed run folder and the -05:00 offset (#12).
- Weekly `SIATA contract` workflow (and `make contract`): checks the live geoportal API
  still returns the fields the pipeline relies on, and opens or updates a `type:bug` issue
  when it does not. Live tests are marked `live` and excluded from the default run (#8).
- `make extract` lands the SIATA stations list and each station's 72 h series in
  `data/01_raw/siata/pm25/<date>/`, incrementally and idempotently: existing files are
  never refetched, writes are atomic, malformed responses are not landed, and failed
  stations fail the run after the others are landed (#6). Offline tests cover idempotence,
  partial failures and malformed responses (#7).
- `aburra_air.data.siata`: SIATA geoportal client (`httpx`) with `tenacity` retries on
  timeouts, 429 and 5xx, an identifying User-Agent and request logging; offline tests on
  recorded responses in `tests/fixtures/siata` (#5).
- Project scaffold from `ds-project-template`: `aburra_air` package with extract, load and
  transform pipeline stubs, config, logging, Streamlit app stub, CI, pre-commit.
- `docs/data.md`: SIATA data access findings and Resolución 2254 de 2017 thresholds.
- CI job `actionlint`: lints the GitHub Actions workflows on every PR.

- Kanban board and repo settings documented in README and CLAUDE.md (#3).

### Removed

- `notebooks/` and their tooling: analyses are scripts in `src/` run with `make`.
