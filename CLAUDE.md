# CLAUDE.md

## Conventions

### Kanban workflow

1. Work is tracked in the GitHub Project linked to this repo. Status columns: Backlog,
   Ready, In Progress, In Review, Done. WIP limit: at most 2 items In Progress.
2. Each roadmap phase is a GitHub Milestone ("Phase N - <name>"). Each phase is broken
   into small issues (half a day to two days of work), each with a type label, milestone,
   Priority and Size, and added to the project.
3. Before starting an issue: move it to In Progress and create branch
   `<type>/<issue-number>-<short-slug>` from an updated `main` (e.g., `feat/12-rent-scraper`).
4. When finished: run `make lint typecheck test`, update `CHANGELOG.md`, open a PR that
   says "Closes #<issue>", move the issue to In Review, then STOP, summarize the changes,
   and wait for my approval.
5. After approval: merge with a merge commit (never squash) so individual commits are
   preserved on `main`. Merged branches are deleted automatically. Never delete unmerged
   branches.
6. Extra work, bugs or ideas found along the way are not done silently: create a new issue
   in Backlog.
7. When every issue of a milestone is Done, close the milestone and create the tag/release
   if the roadmap says so.

### Code and data

8. Small commits with conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`,
   `refactor:`, `chore:`, `ci:`, `data:`).
9. Dependencies only via `uv add` (dev tools with `--group dev`).
10. No notebooks. All logic, including exploratory and statistical analyses, lives in
    `src/` and runs with `make`; outputs go to `data/08_reporting` and conclusions to `docs/`.
11. Type hints and docstrings on all public functions; tests for every `src` module; target
    coverage >= 80%.
12. Everything in English: code, comments, docs, README, commits.
13. NEVER invent results. Every metric, number, or figure in the README must come from an
    actual run, saved in `data/08_reporting` (metrics as JSON/CSV, figures as PNG).
14. Data ethics: scraping only if robots.txt and terms of use allow it, with rate limiting
    and an identified user agent; never collect or publish personal data; do not commit
    data whose license forbids redistribution (commit the code plus a small sample
    instead); secrets only in `.env`, never committed (provide `.env.example`).

## Project

Production-style ELT for air quality in the Aburrá Valley. Full spec in `SPEC.md`; data
sources, endpoint limits and Resolución 2254 de 2017 thresholds in `docs/data.md`.

- Layers: `01_raw` = landing JSON, `03_primary` = dbt staging, `02_intermediate` = dbt
  intermediate, `05_model_input` = dbt marts (Parquet), `08_reporting` = analysis outputs.
- Live source is the SIATA geoportal API, PM2.5 only, 72 h window: the extractor must be
  idempotent and the load must deduplicate on `(station_code, timestamp_hour)`.
- Times are America/Bogota (UTC-5, no DST); store timestamps with the offset.
- SIATA terms are unconfirmed: one request per station per day, identifying User-Agent,
  credit SIATA, and do not publish full data as a release asset until SIATA confirms.
- Roadmap: Phase 0 Setup → 1 Extract → 2 Load and backfill → 3 dbt models →
  4 Orchestration → 5 Analysis → 6 Dashboard → 7 Docs and v1.0.0.
- GitHub Project URL: TODO (Phase 0).
