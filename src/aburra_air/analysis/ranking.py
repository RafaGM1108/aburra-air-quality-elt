"""Rank stations by 24 h exceedance days and mean PM2.5 over the analysis window."""

import logging
from pathlib import Path

import duckdb

from aburra_air.analysis.plot import barh
from aburra_air.utils.config import AnalysisConfig

logger = logging.getLogger(__name__)

# Stations below min_coverage are listed with a NULL rank, after the ranked ones.
RANKING_SQL = """
WITH stats AS (
    SELECT
        d.station_code,
        s.station_id,
        s.station_name,
        s.municipality,
        count(*) FILTER (WHERE d.is_valid_day) AS valid_days,
        round(count(*) FILTER (WHERE d.is_valid_day) / ($end::DATE - $start::DATE + 1), 3)
            AS coverage,
        round(avg(d.pm25_mean), 1) AS pm25_mean,
        count(*) FILTER (WHERE d.exceeds_24h_limit) AS exceedance_days,
        round(100 * count(*) FILTER (WHERE d.exceeds_24h_limit)
            / nullif(count(*) FILTER (WHERE d.is_valid_day), 0), 1) AS exceedance_pct
    FROM read_parquet($daily) AS d
    LEFT JOIN read_parquet($stations) AS s USING (station_code)
    WHERE d.date_local BETWEEN $start AND $end
    GROUP BY ALL
)
SELECT
    CASE WHEN coverage >= $min_coverage THEN
        row_number() OVER (
            PARTITION BY coverage >= $min_coverage
            ORDER BY exceedance_days DESC, pm25_mean DESC
        )
    END AS rank,
    *
FROM stats
ORDER BY rank NULLS LAST, station_code
"""


def station_ranking(model_input: Path, reporting: Path, analysis: AnalysisConfig) -> list[Path]:
    """Write ``station_ranking.csv`` and a bar chart of exceedance days of ranked stations.

    Args:
        model_input: Folder with ``fct_pm25_daily.parquet`` and ``dim_stations.parquet``.
        reporting: The ``08_reporting`` folder.
        analysis: Window and coverage threshold.

    Returns:
        The written files.
    """
    reporting.mkdir(parents=True, exist_ok=True)
    table = reporting / "station_ranking.csv"
    params = {
        "daily": str(model_input / "fct_pm25_daily.parquet"),
        "stations": str(model_input / "dim_stations.parquet"),
        "start": analysis.start,
        "end": analysis.end,
        "min_coverage": analysis.min_coverage,
    }
    with duckdb.connect() as con:
        con.execute(f"CREATE TABLE ranking AS {RANKING_SQL}", params)
        con.execute("COPY ranking TO ? (HEADER)", [str(table)])
        ranked = con.execute(
            "SELECT coalesce(station_id, station_code::VARCHAR), exceedance_days "
            "FROM ranking WHERE rank IS NOT NULL ORDER BY rank"
        ).fetchall()
    chart = barh(
        reporting / "station_ranking.png",
        labels=[str(label) for label, _ in ranked],
        values=[float(value) for _, value in ranked],
        xlabel="Days with daily mean PM2.5 > 37 µg/m³",
        title=f"Exceedance days by station, {analysis.start} to {analysis.end}",
        note=f"Source: SIATA. Stations with ≥ {analysis.min_coverage:.0%} valid days.",
    )
    logger.info("ranking ranked=%d file=%s", len(ranked), table)
    return [table, chart]
