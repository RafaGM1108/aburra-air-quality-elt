# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
