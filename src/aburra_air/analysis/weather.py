"""Relate daily valley PM2.5 means to Open-Meteo weather covariates."""

from pathlib import Path

import duckdb

from aburra_air.utils.config import AnalysisConfig

DAILY_SQL = """
WITH pm25 AS (
    SELECT date_local, avg(pm25_mean) AS pm25_mean, count(*) AS stations_with_valid_mean
    FROM read_parquet($pm25)
    WHERE is_valid_day AND date_local BETWEEN $start AND $end
    GROUP BY date_local
), paired AS (
    SELECT p.date_local, p.pm25_mean, p.stations_with_valid_mean,
        w.valid_hours AS weather_valid_hours, w.precipitation_total,
        w.boundary_layer_height_mean, w.boundary_layer_height_min
    FROM pm25 AS p INNER JOIN read_parquet($weather) AS w USING (date_local)
)
SELECT * FROM paired ORDER BY date_local
"""

SUMMARY_SQL = """
SELECT count(*) AS paired_days,
    corr(pm25_mean, boundary_layer_height_mean) AS pm25_boundary_layer_height_correlation,
    corr(pm25_mean, precipitation_total) AS pm25_precipitation_correlation
FROM paired
"""


def weather_relationship(
    model_input: Path, reporting: Path, analysis: AnalysisConfig
) -> list[Path]:
    """Write paired daily weather/PM2.5 data and Pearson correlations.

    The PM2.5 value is the unweighted mean of available station daily means, so this is
    an exploratory valley-level association rather than a causal model.

    Args:
        model_input: Folder containing the daily PM2.5 and Open-Meteo marts.
        reporting: Destination ``08_reporting`` folder.
        analysis: Window used for the project's reporting.

    Returns:
        Paths to the paired daily data and one-row correlation summary.
    """
    reporting.mkdir(parents=True, exist_ok=True)
    params = {
        "pm25": str(model_input / "fct_pm25_daily.parquet"),
        "weather": str(model_input / "fct_open_meteo_daily.parquet"),
        "start": analysis.start,
        "end": analysis.end,
    }
    daily_path = reporting / "pm25_weather_daily.csv"
    summary_path = reporting / "pm25_weather_summary.csv"
    with duckdb.connect() as con:
        con.execute(f"CREATE TABLE paired AS {DAILY_SQL}", params)
        con.execute("COPY paired TO ? (HEADER)", [str(daily_path)])
        con.execute(f"COPY ({SUMMARY_SQL}) TO ? (HEADER)", [str(summary_path)])
    return [daily_path, summary_path]
