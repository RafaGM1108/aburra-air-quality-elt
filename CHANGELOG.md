# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

### Removed

- `notebooks/` and their tooling: analyses are scripts in `src/` run with `make`.
