"""Diurnal, weekly and monthly PM2.5 patterns over the analysis window.

Means pool every station-hour (or station-day) of the window; that is fine for a
pattern but not for exceedances, which Res. 2254 checks per station. Each table has a
``coverage`` column and each figure states the pooled coverage: for the diurnal cycle,
valid station-hours over (stations with data in the window x hours of that day type);
for weekdays and months, valid station-days over station-days present in the marts.
"""

import logging
from pathlib import Path

import duckdb

from aburra_air.analysis.plot import barh, lines
from aburra_air.utils.config import AnalysisConfig

logger = logging.getLogger(__name__)

# Stations with any valid hour in the window form the network the coverage refers to.
DIURNAL_SQL = """
WITH profile AS (
    SELECT * FROM read_parquet($hourly)
    WHERE month BETWEEN date_trunc('month', $start::DATE) AND $end
),
network AS (SELECT count(DISTINCT station_code) AS n FROM profile WHERE valid_hours > 0),
days AS (
    SELECT
        count(*) FILTER (WHERE dayofweek(d) IN (0, 6)) AS weekend,
        count(*) FILTER (WHERE dayofweek(d) NOT IN (0, 6)) AS weekday
    FROM range($start::DATE, $end::DATE + 1, INTERVAL 1 DAY) AS t(d)
)
SELECT
    hour_of_day,
    CASE WHEN is_weekend THEN 'weekend' ELSE 'weekday' END AS day_type,
    sum(valid_hours) AS valid_hours,
    any_value(network.n)
        * CASE WHEN is_weekend THEN any_value(days.weekend) ELSE any_value(days.weekday) END
        AS possible_hours,
    round(sum(valid_hours) / possible_hours, 3) AS coverage,
    round(sum(pm25_sum) / nullif(sum(valid_hours), 0), 1) AS pm25_mean
FROM profile, network, days
GROUP BY hour_of_day, is_weekend
ORDER BY day_type, hour_of_day
"""

WEEKDAY_SQL = """
WITH days AS (SELECT * FROM read_parquet($daily) WHERE date_local BETWEEN $start AND $end)
SELECT
    isodow(date_local) AS iso_weekday,
    dayname(date_local) AS weekday,
    count(*) FILTER (WHERE is_valid_day) AS valid_days,
    count(*) AS station_days,
    round(valid_days / station_days, 3) AS coverage,
    round(avg(pm25_mean), 1) AS pm25_mean
FROM days
GROUP BY ALL
ORDER BY iso_weekday
"""

MONTHLY_SQL = """
WITH days AS (SELECT * FROM read_parquet($daily) WHERE date_local BETWEEN $start AND $end)
SELECT
    strftime(date_trunc('month', date_local), '%Y-%m') AS month,
    count(*) FILTER (WHERE is_valid_day) AS valid_days,
    count(*) AS station_days,
    round(valid_days / station_days, 3) AS coverage,
    round(avg(pm25_mean), 1) AS pm25_mean,
    count(*) FILTER (WHERE exceeds_24h_limit) AS exceedance_days
FROM days
GROUP BY ALL
ORDER BY month
"""


def overall_coverage(
    con: duckdb.DuckDBPyConnection, table: str, valid: str, possible: str
) -> float:
    """Return the pooled coverage of a pattern table: sum of valid over sum of possible.

    Args:
        con: Connection holding ``table`` (one of this module's tables).
        table: Table name.
        valid: Column with valid units per row.
        possible: Column with possible units per row.

    Returns:
        The coverage, 0 when nothing is possible.
    """
    # Identifiers come from this module, never from input.
    sql = f"SELECT sum({valid}) / nullif(sum({possible}), 0) FROM {table}"  # nosec B608
    row = con.execute(sql).fetchone()
    return float(row[0] or 0) if row else 0.0


def patterns(model_input: Path, reporting: Path, analysis: AnalysisConfig) -> list[Path]:
    """Write the diurnal, weekday and monthly tables (CSV) and figures (PNG).

    Args:
        model_input: Folder with ``agg_pm25_hour_of_day`` and ``fct_pm25_daily`` Parquet.
        reporting: The ``08_reporting`` folder.
        analysis: Window.

    Returns:
        The written files.
    """
    reporting.mkdir(parents=True, exist_ok=True)
    params = {
        "hourly": str(model_input / "agg_pm25_hour_of_day.parquet"),
        "daily": str(model_input / "fct_pm25_daily.parquet"),
        "start": analysis.start,
        "end": analysis.end,
    }
    window = f"{analysis.start} to {analysis.end}"
    written: list[Path] = []
    with duckdb.connect() as con:
        for name, sql in (
            ("diurnal_profile", DIURNAL_SQL),
            ("weekday_profile", WEEKDAY_SQL),
            ("monthly_profile", MONTHLY_SQL),
        ):
            used = {k: v for k, v in params.items() if f"${k}" in sql}
            con.execute(f"CREATE TABLE {name} AS {sql}", used)
            path = reporting / f"{name}.csv"
            con.execute(f"COPY {name} TO ? (HEADER)", [str(path)])
            written.append(path)

        hours = list(range(24))
        series = {
            day_type: [
                row[0]
                for row in con.execute(
                    "SELECT pm25_mean FROM diurnal_profile WHERE day_type = ? ORDER BY hour_of_day",
                    [day_type],
                ).fetchall()
            ]
            for day_type in ("weekday", "weekend")
        }
        coverage = overall_coverage(con, "diurnal_profile", "valid_hours", "possible_hours")
        written.append(
            lines(
                reporting / "diurnal_profile.png",
                x=[float(h) for h in hours],
                series={k: v for k, v in series.items() if len(v) == len(hours)},
                xlabel="Hour of day (America/Bogota)",
                ylabel="Mean PM2.5 (µg/m³)",
                title=f"Diurnal PM2.5 cycle, all stations, {window}",
                note=f"Source: SIATA. Coverage: {coverage:.0%} of station-hours valid.",
            )
        )

        weekdays = con.execute(
            "SELECT weekday, pm25_mean FROM weekday_profile ORDER BY iso_weekday"
        ).fetchall()
        coverage = overall_coverage(con, "weekday_profile", "valid_days", "station_days")
        written.append(
            barh(
                reporting / "weekday_profile.png",
                labels=[str(day) for day, _ in weekdays],
                values=[float(mean or 0) for _, mean in weekdays],
                xlabel="Mean of daily means, PM2.5 (µg/m³)",
                title=f"PM2.5 by day of week, all stations, {window}",
                note=f"Source: SIATA. Coverage: {coverage:.0%} of station-days valid.",
            )
        )

        months = con.execute(
            "SELECT month, pm25_mean FROM monthly_profile ORDER BY month"
        ).fetchall()
        coverage = overall_coverage(con, "monthly_profile", "valid_days", "station_days")
        written.append(
            lines(
                reporting / "monthly_profile.png",
                x=[float(i) for i in range(len(months))],
                series={"mean of daily means": [m for _, m in months]},
                xlabel="Month index from " + (str(months[0][0]) if months else "-"),
                ylabel="PM2.5 (µg/m³)",
                title=f"Monthly PM2.5, all stations, {window}",
                note=f"Source: SIATA. Coverage: {coverage:.0%} of station-days valid.",
            )
        )
    logger.info("patterns files=%d", len(written))
    return written
