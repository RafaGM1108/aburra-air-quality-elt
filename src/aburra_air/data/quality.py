"""Data-quality checks on the DuckDB file after an ELT run.

Each check returns a failure message or ``None``; :func:`check_all` runs them all, so one
run reports every problem at once.
"""

import logging
from collections.abc import Callable
from datetime import datetime

import duckdb

from aburra_air.utils.config import QualityConfig

logger = logging.getLogger(__name__)

Check = Callable[[duckdb.DuckDBPyConnection, QualityConfig, datetime], str | None]


class QualityError(RuntimeError):
    """At least one data-quality check failed."""


def scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list[object] | None = None) -> object:
    """Return the single value of a one-row, one-column query.

    Args:
        con: Open DuckDB connection.
        sql: Query returning one row with one column.
        params: Query parameters.

    Returns:
        The value, possibly ``None``.
    """
    row = con.execute(sql, params or []).fetchone()
    return None if row is None else row[0]


def check_freshness(
    con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime
) -> str | None:
    """Fail if the latest live hour is older than ``max_lag_hours``."""
    lag = scalar(
        con,
        "SELECT date_diff('hour', max(timestamp_hour), ?) FROM raw.siata_pm25_hourly",
        [now],
    )
    if lag is None:
        return "freshness: no live readings loaded"
    if not isinstance(lag, int) or lag > quality.max_lag_hours:
        return f"freshness: latest live hour is {lag} h old (max {quality.max_lag_hours} h)"
    return None


def check_latest_run_rows(
    con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime
) -> str | None:
    """Fail if the latest run folder provided fewer hourly rows than expected."""
    rows = scalar(
        con,
        "SELECT count(*) FROM raw.siata_pm25_hourly "
        "WHERE landed_on = (SELECT max(landed_on) FROM raw.siata_pm25_hourly)",
    )
    if not isinstance(rows, int) or rows < quality.min_rows_latest_run:
        return f"row count: latest run provided {rows} rows (min {quality.min_rows_latest_run})"
    return None


def check_station_coverage(
    con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime
) -> str | None:
    """Fail if too few stations reported a valid hour in the last 24 h of the series."""
    stations = scalar(
        con,
        "SELECT count(DISTINCT station_code) FROM staging.stg_siata__pm25_live "
        "WHERE pm25 IS NOT NULL AND timestamp_hour > "
        "(SELECT max(timestamp_hour) FROM raw.siata_pm25_hourly) - INTERVAL 24 HOUR",
    )
    if not isinstance(stations, int) or stations < quality.min_stations_last_24h:
        return (
            f"station coverage: {stations} stations with data in the last 24 h "
            f"(min {quality.min_stations_last_24h})"
        )
    return None


def check_no_duplicate_keys(
    con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime
) -> str | None:
    """Fail if the hourly or daily marts repeat a key."""
    duplicates = scalar(
        con,
        "SELECT (SELECT count(*) - count(DISTINCT (station_code, timestamp_hour)) "
        "FROM marts.fct_pm25_hourly) + (SELECT count(*) - count(DISTINCT (station_code, "
        "date_local)) FROM marts.fct_pm25_daily)",
    )
    if duplicates != 0:
        return f"duplicates: {duplicates} repeated keys in fct_pm25_hourly/fct_pm25_daily"
    return None


CHECKS: tuple[Check, ...] = (
    check_freshness,
    check_latest_run_rows,
    check_station_coverage,
    check_no_duplicate_keys,
)


def check_all(con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime) -> None:
    """Run every check and fail with all messages if any failed.

    Args:
        con: Connection to the DuckDB file after ``make load transform``.
        quality: Thresholds from ``conf/base.yaml``.
        now: Current time (timezone-aware).

    Raises:
        QualityError: Listing every failed check.
    """
    failures: list[str] = []
    for check in CHECKS:
        try:
            message = check(con, quality, now)
        except duckdb.Error as error:  # e.g. a table missing because transform did not run
            message = f"{check.__name__}: {error}"
        if message:
            failures.append(message)
    for message in failures:
        logger.error("quality check failed: %s", message)
    if failures:
        raise QualityError("Data-quality checks failed:\n- " + "\n- ".join(failures))
    logger.info("quality checks passed: %d", len(CHECKS))
