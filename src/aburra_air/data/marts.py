"""Read the published marts for the dashboard: daily and monthly aggregates only.

The dashboard never needs hourly data. It reads the marts from ``05_model_input`` and
downloads any missing one from the ``data-latest`` release, so a fresh checkout (e.g. on
Streamlit Community Cloud) works without running the pipeline.
"""

import logging
import time
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pandas as pd

logger = logging.getLogger(__name__)

MARTS = ("agg_pm25_hour_of_day", "agg_pm25_station_monthly", "dim_stations", "fct_pm25_daily")
ALL_TIME = (date(1900, 1, 1), date(2100, 1, 1))
RELEASE_URL = (
    "https://github.com/RafaGM1108/aburra-air-quality-elt/releases/download/data-latest/{name}"
)


def ensure_marts(folder: Path, client: httpx.Client, max_age_hours: float | None = None) -> Path:
    """Download marts missing from ``folder`` (or older than ``max_age_hours``) from the release.

    A stale mart that cannot be refreshed is kept, so the app still works offline.

    Args:
        folder: Where the marts live (``05_model_input``).
        client: HTTP client that follows redirects.
        max_age_hours: Re-download marts last written longer ago than this; ``None`` never
            refreshes an existing mart.

    Returns:
        ``folder``.

    Raises:
        httpx.HTTPError: If a missing mart cannot be downloaded.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for name in MARTS:
        path = folder / f"{name}.parquet"
        if path.exists():
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            if max_age_hours is None or age_hours <= max_age_hours:
                continue
        try:
            response = client.get(RELEASE_URL.format(name=path.name))
            response.raise_for_status()
        except httpx.HTTPError:
            if not path.exists():
                raise
            logger.warning("refresh failed, keeping stale mart=%s", path.name)
            continue
        partial = path.with_name(path.name + ".part")
        partial.write_bytes(response.content)
        partial.replace(path)
        logger.info("downloaded mart=%s bytes=%d", path.name, len(response.content))
    return folder


def query(folder: Path, sql: str, params: dict[str, object] | None = None) -> pd.DataFrame:
    """Run SQL with one view per mart (``daily``, ``stations``, ``monthly``, ``hourly``).

    Args:
        folder: Folder with the marts.
        sql: Query over the views.
        params: Named parameters.

    Returns:
        The result as a DataFrame.
    """
    views = {
        "daily": "fct_pm25_daily",
        "stations": "dim_stations",
        "monthly": "agg_pm25_station_monthly",
        "hourly": "agg_pm25_hour_of_day",
    }
    with duckdb.connect() as con:
        for view, mart in views.items():
            con.read_parquet(str(folder / f"{mart}.parquet")).create_view(view)
        return con.execute(sql, params or {}).df()


def latest_ica(folder: Path) -> pd.DataFrame:
    """Latest valid day of every station with a location, for the map.

    Args:
        folder: Folder with the marts.

    Returns:
        One row per located station; stations without a valid day have NULL values.
    """
    return query(
        folder,
        """
        WITH latest AS (
            SELECT * FROM daily WHERE is_valid_day
            QUALIFY row_number() OVER (PARTITION BY station_code ORDER BY date_local DESC) = 1
        )
        SELECT s.station_code, s.station_id, s.station_name, s.municipality,
            s.latitude, s.longitude, l.date_local, round(l.pm25_mean, 1) AS pm25_mean,
            l.ica, coalesce(l.ica_category, 'Sin datos') AS ica_category
        FROM stations AS s LEFT JOIN latest AS l USING (station_code)
        WHERE s.latitude IS NOT NULL
        ORDER BY s.station_code
        """,
    )


def station_options(folder: Path) -> pd.DataFrame:
    """Stations that have at least one daily row, labelled for a select box.

    Args:
        folder: Folder with the marts.

    Returns:
        ``station_code`` and ``label``, ordered by label.
    """
    return query(
        folder,
        """
        SELECT DISTINCT d.station_code,
            coalesce(s.station_id || ' · ' || s.station_name, 'Station ' || d.station_code)
                AS label
        FROM daily AS d LEFT JOIN stations AS s USING (station_code)
        ORDER BY label
        """,
    )


def daily_series(
    folder: Path, station_code: int, period: tuple[date, date] = ALL_TIME
) -> pd.DataFrame:
    """Daily means of one station (valid days only) within ``period``, oldest first.

    Args:
        folder: Folder with the marts.
        station_code: SIATA station code.
        period: First and last day, inclusive.

    Returns:
        ``date_local``, ``pm25_mean``, ``ica_category``.
    """
    return query(
        folder,
        """
        SELECT date_local, pm25_mean, ica_category FROM daily
        WHERE station_code = $code AND is_valid_day AND date_local BETWEEN $start AND $end
        ORDER BY date_local
        """,
        {"code": station_code, "start": period[0], "end": period[1]},
    )


def monthly_exceedances(
    folder: Path, station_code: int, period: tuple[date, date] = ALL_TIME
) -> pd.DataFrame:
    """Monthly valid days and exceedance days of one station, for months starting in ``period``.

    Args:
        folder: Folder with the marts.
        station_code: SIATA station code.
        period: First and last day, inclusive.

    Returns:
        ``month``, ``valid_days``, ``exceedance_days``, ``pm25_mean``.
    """
    return query(
        folder,
        """
        SELECT month, valid_days, exceedance_days, round(pm25_mean, 1) AS pm25_mean
        FROM monthly WHERE station_code = $code AND month BETWEEN $start AND $end
        ORDER BY month
        """,
        {"code": station_code, "start": period[0], "end": period[1]},
    )


def hour_profile(folder: Path, station_code: int) -> pd.DataFrame:
    """Mean PM2.5 by hour of day of one station, weekdays vs weekends, all months pooled.

    Args:
        folder: Folder with the marts.
        station_code: SIATA station code.

    Returns:
        ``hour_of_day``, ``day_type``, ``pm25_mean``, ``valid_hours``.
    """
    return query(
        folder,
        """
        SELECT hour_of_day,
            CASE WHEN is_weekend THEN 'weekend' ELSE 'weekday' END AS day_type,
            round(sum(pm25_sum) / nullif(sum(valid_hours), 0), 1) AS pm25_mean,
            sum(valid_hours) AS valid_hours
        FROM hourly WHERE station_code = $code
        GROUP BY ALL ORDER BY day_type, hour_of_day
        """,
        {"code": station_code},
    )
