"""Next-day PM2.5 baselines, backtested on the daily means of the analysis window.

"Next 24 h" is read as the next calendar day's mean, the quantity the 24 h limit and the
ICA use. Three naive forecasts are compared on exactly the same station-days (those where
all three exist), so none is favoured by the days it skips:

- ``persistence``: tomorrow equals today;
- ``mean_7d``: tomorrow equals the mean of the last 7 days (needs ≥ 5 valid days);
- ``seasonal_naive_7d``: tomorrow equals the same weekday last week.

``skill_vs_persistence`` is 1 - MAE / MAE(persistence): positive beats persistence.
"""

import logging
from pathlib import Path

import duckdb

from aburra_air.utils.config import AnalysisConfig

logger = logging.getLogger(__name__)

BACKTEST_SQL = """
WITH days AS (
    SELECT station_code, date_local, pm25_mean FROM read_parquet($daily)
    WHERE is_valid_day AND date_local BETWEEN $start AND $end
),
features AS (
    SELECT
        t.station_code,
        t.date_local,
        t.pm25_mean AS actual,
        yesterday.pm25_mean AS persistence,
        last_week.pm25_mean AS seasonal_naive_7d,
        (SELECT CASE WHEN count(*) >= 5 THEN avg(w.pm25_mean) END FROM days AS w
         WHERE w.station_code = t.station_code
           AND w.date_local BETWEEN (t.date_local - INTERVAL 7 DAY)::DATE
                                AND (t.date_local - INTERVAL 1 DAY)::DATE) AS mean_7d
    FROM days AS t
    JOIN days AS yesterday ON yesterday.station_code = t.station_code
        AND yesterday.date_local = (t.date_local - INTERVAL 1 DAY)::DATE
    JOIN days AS last_week ON last_week.station_code = t.station_code
        AND last_week.date_local = (t.date_local - INTERVAL 7 DAY)::DATE
),
comparable AS (SELECT * FROM features WHERE mean_7d IS NOT NULL),
errors AS (
    UNPIVOT comparable ON persistence, mean_7d, seasonal_naive_7d
    INTO NAME method VALUE forecast
),
metrics AS (
    SELECT
        method,
        count(*) AS n,
        avg(abs(forecast - actual)) AS mae,
        sqrt(avg((forecast - actual) ^ 2)) AS rmse,
        avg(forecast - actual) AS bias
    FROM errors GROUP BY method
)
SELECT
    method,
    n,
    round(mae, 2) AS mae,
    round(rmse, 2) AS rmse,
    round(bias, 2) AS bias,
    round(1 - mae / (SELECT mae FROM metrics WHERE method = 'persistence'), 3)
        AS skill_vs_persistence
FROM metrics
ORDER BY mae
"""


def forecast_baselines(model_input: Path, reporting: Path, analysis: AnalysisConfig) -> list[Path]:
    """Write ``forecast_baselines.csv``: MAE, RMSE, bias and skill of each baseline.

    Args:
        model_input: Folder with ``fct_pm25_daily.parquet``.
        reporting: The ``08_reporting`` folder.
        analysis: Window.

    Returns:
        The written file.
    """
    reporting.mkdir(parents=True, exist_ok=True)
    path = reporting / "forecast_baselines.csv"
    params = {
        "daily": str(model_input / "fct_pm25_daily.parquet"),
        "start": analysis.start,
        "end": analysis.end,
    }
    with duckdb.connect() as con:
        con.execute(f"CREATE TABLE baselines AS {BACKTEST_SQL}", params)
        con.execute("COPY baselines TO ? (HEADER)", [str(path)])
        rows = con.execute("SELECT method, n, mae FROM baselines").fetchall()
    logger.info("forecast baselines=%s", rows)
    return [path]
