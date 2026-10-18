"""Select the marts that may be published and check they hold no hourly series.

SIATA's redistribution terms are unconfirmed (docs/data.md), so only daily or coarser
aggregates leave the pipeline: never raw JSON, the DuckDB file or an hourly series.
"""

import logging
import shutil
from pathlib import Path

import duckdb

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
