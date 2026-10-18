"""Select the marts that may be published and check they hold no hourly series.

SIATA's redistribution terms are unconfirmed (docs/data.md), so only daily or coarser
aggregates leave the pipeline: never raw JSON, the DuckDB file or an hourly series.
"""

import hashlib
import json
import logging
import shutil
from pathlib import Path

import duckdb
import httpx

PUBLISHABLE = (
    "agg_pm25_hour_of_day",
    "agg_pm25_station_monthly",
    "dim_stations",
    "fct_pm25_daily",
)
FORBIDDEN_COLUMNS = frozenset({"timestamp_hour", "hour_local"})

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """A mart is missing or would publish hourly data."""


def check_publishable(path: Path) -> None:
    """Fail if a Parquet file has a column that identifies an hour.

    Args:
        path: Parquet file to check.

    Raises:
        PublishError: If the file has a forbidden column.
    """
    with duckdb.connect() as con:
        columns = {
            row[0]
            for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
        }
    if hourly := columns & FORBIDDEN_COLUMNS:
        raise PublishError(f"{path.name} has hourly columns {sorted(hourly)}; not publishable")


def stage_publication(model_input: Path, out_dir: Path) -> list[Path]:
    """Copy the publishable marts to ``out_dir`` after checking each one.

    Args:
        model_input: The ``05_model_input`` folder with the dbt marts.
        out_dir: Folder to fill; emptied first so nothing else can slip in.

    Returns:
        The staged files.

    Raises:
        PublishError: If a mart is missing or has hourly columns.
    """
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    staged: list[Path] = []
    for name in PUBLISHABLE:
        source = model_input / f"{name}.parquet"
        if not source.exists():
            raise PublishError(f"{source} is missing; run `make transform` first")
        check_publishable(source)
        staged.append(Path(shutil.copy2(source, out_dir / source.name)))
    logger.info("publish staged=%s", [p.name for p in staged])
    return staged


RELEASE_API = (
    "https://api.github.com/repos/RafaGM1108/aburra-air-quality-elt/releases/tags/data-latest"
)
REPORTING_SUFFIXES = (".csv", ".png")


def fetch_reporting(client: httpx.Client, reporting: Path) -> list[Path]:
    """Download the analysis outputs of the latest Daily ELT run from the ``data-latest`` release.

    Analyses that need hourly data only run in the Daily ELT, so the committed
    ``08_reporting`` files are copies of what that run published. ``provenance.json``
    records when each file was uploaded by that run and its SHA-256 digest.

    Args:
        client: HTTP client (GitHub API and release downloads, redirects followed).
        reporting: The ``08_reporting`` folder.

    Returns:
        The written files, ``provenance.json`` last.

    Raises:
        httpx.HTTPError: If the release or an asset cannot be fetched.
    """
    response = client.get(RELEASE_API)
    response.raise_for_status()
    release = response.json()
    reporting.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    assets: list[dict[str, str]] = []
    for asset in release["assets"]:
        name = str(asset["name"])
        if not name.endswith(REPORTING_SUFFIXES):
            continue
        body = client.get(asset["browser_download_url"]).raise_for_status().content
        path = reporting / name
        path.write_bytes(body)
        written.append(path)
        digest = hashlib.sha256(body).hexdigest()
        assets.append({"name": name, "updated_at": str(asset["updated_at"]), "sha256": digest})
    provenance = reporting / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "source": release["html_url"],
                "published_at": release["published_at"],
                "files": sorted(assets, key=lambda a: a["name"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("fetch reporting files=%d published_at=%s", len(written), release["published_at"])
    return [*written, provenance]
