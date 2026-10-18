# Deploy the dashboard

The dashboard (`src/aburra_air/app/main.py`) reads only the published aggregates. On
start it downloads any missing mart from the
[`data-latest`](https://github.com/RafaGM1108/aburra-air-quality-elt/releases/tag/data-latest)
release, refreshed by the Daily ELT, so the host needs no pipeline, database or secret.

## Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns the repo.
2. **Create app** → **Deploy a public app from GitHub**:
   - Repository: `RafaGM1108/aburra-air-quality-elt`
   - Branch: `main`
   - Main file path: `src/aburra_air/app/main.py`
   - Advanced settings → Python version: **3.12**
3. Deploy. Community Cloud installs `requirements.txt` (exported from `uv.lock` with
   `make requirements`; CI fails if it is stale) and reads `.streamlit/config.toml`.
4. Put the app URL in the README.

The app re-downloads any mart older than 24 hours (checked at most once an hour), so it
follows the Daily ELT without a reboot; if the download fails it keeps the copy it has.

## Locally

```bash
make install
make app   # http://localhost:8501
```
