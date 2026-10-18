"""Critical PM2.5 episodes per Resolución 2254 de 2017, Art. 10, 11 and 13.

Levels use the 24 h moving average (Art. 11, automatic monitors): prevención 38-55,
alerta 56-150, emergencia ≥ 151 µg/m³ (Table 4). Rule as implemented (docs/methodology.md):

- the 24 h moving average at hour t uses hours t-23..t and needs ≥ 18 valid hours;
- an episode of a level starts at the first hour whose moving average is in that level or
  above, if more than 75% of the next 48 moving averages are at that level or above;
- while it lasts, a higher level is declared the same way and the episode keeps the highest;
- it ends at the first hour whose moving average is below the lower limit of its starting
  level, if more than 75% of the next 48 moving averages are also below it (Art. 13);
- a missing moving average counts against both declaring and ending, and an hour without
  48 hours of future data cannot start or end an episode.
"""

import csv
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from aburra_air.utils.config import AnalysisConfig

logger = logging.getLogger(__name__)

LEVELS = (("prevencion", 38), ("alerta", 56), ("emergencia", 151))  # lower limits, µg/m³
LOOKAHEAD_HOURS = 48
SHARE = 0.75

MOVING_AVERAGE_SQL = """
WITH readings AS (
    SELECT station_code, timestamp_hour, pm25 FROM read_parquet($hourly)
    WHERE date_local BETWEEN $start AND $end
),
grid AS (  -- every hour between each station's first and last reading
    SELECT station_code, unnest(generate_series(min(timestamp_hour), max(timestamp_hour),
        INTERVAL 1 HOUR)) AS timestamp_hour
    FROM readings GROUP BY station_code
)
SELECT
    g.station_code,
    strftime(timezone('America/Bogota', g.timestamp_hour), '%Y-%m-%dT%H:00-05:00') AS hour,
    CASE WHEN count(r.pm25) OVER w >= 18 THEN avg(r.pm25) OVER w END AS mavg24
FROM grid AS g
LEFT JOIN readings AS r USING (station_code, timestamp_hour)
WINDOW w AS (
    PARTITION BY g.station_code ORDER BY g.timestamp_hour
    RANGE BETWEEN INTERVAL 23 HOURS PRECEDING AND CURRENT ROW
)
ORDER BY g.station_code, g.timestamp_hour
"""


@dataclass(frozen=True)
class Episode:
    """One declared episode at one station."""

    start: int
    end: int | None  # index of the ending hour; None if still open at the end of the data
    level: str  # highest level declared during the episode
    peak: float  # highest 24 h moving average during the episode


def level_index(value: float | None) -> int:
    """Return the index in :data:`LEVELS` of a moving average, or -1 below prevención.

    Breakpoints are integers with gaps (55 → 56), so the value is truncated first, as for
    the ICA.
    """
    if value is None or math.isnan(value):
        return -1
    found = -1
    for index, (_, lower) in enumerate(LEVELS):
        if math.trunc(value) >= lower:
            found = index
    return found


def share_at_or_above(mavg: Sequence[float | None], t: int, lower: float) -> float | None:
    """Share of the 48 hours after ``t`` whose moving average is ≥ ``lower`` (truncated).

    Returns ``None`` if fewer than 48 hours of data follow ``t``.
    """
    window = mavg[t + 1 : t + 1 + LOOKAHEAD_HOURS]
    if len(window) < LOOKAHEAD_HOURS:
        return None
    hits = sum(1 for v in window if v is not None and math.trunc(v) >= lower)
    return hits / LOOKAHEAD_HOURS


def share_below(mavg: Sequence[float | None], t: int, lower: float) -> float | None:
    """Share of the 48 hours after ``t`` whose moving average is valid and < ``lower``."""
    window = mavg[t + 1 : t + 1 + LOOKAHEAD_HOURS]
    if len(window) < LOOKAHEAD_HOURS:
        return None
    hits = sum(1 for v in window if v is not None and math.trunc(v) < lower)
    return hits / LOOKAHEAD_HOURS


def detect_episodes(mavg: Sequence[float | None]) -> list[Episode]:
    """Detect episodes in one station's hourly series of 24 h moving averages.

    Args:
        mavg: Moving average per hour, consecutive hours, ``None`` when not valid.

    Returns:
        Episodes in time order.
    """
    episodes: list[Episode] = []
    t = 0
    while t < len(mavg):
        level = level_index(mavg[t])
        declared = -1
        for candidate in range(level, -1, -1):  # the highest level the 48 h rule confirms
            share = share_at_or_above(mavg, t, LEVELS[candidate][1])
            if share is not None and share > SHARE:
                declared = candidate
                break
        if declared < 0:
            t += 1
            continue
        start, lower = t, LEVELS[declared][1]
        highest, peak, end = declared, float(mavg[t] or 0), None
        for u in range(t + 1, len(mavg)):
            value = mavg[u]
            if value is not None:
                peak = max(peak, value)
                above = level_index(value)
                if above > highest:
                    share = share_at_or_above(mavg, u, LEVELS[above][1])
                    if share is not None and share > SHARE:
                        highest = above
            if value is not None and math.trunc(value) < lower:
                share = share_below(mavg, u, lower)
                if share is not None and share > SHARE:
                    end = u
                    break
        episodes.append(Episode(start, end, LEVELS[highest][0], round(peak, 1)))
        if end is None:
            break
        t = end + 1
    return episodes


COLUMNS = ("station_code", "level", "start", "end", "duration_hours", "peak_mavg24")


def episodes(model_input: Path, reporting: Path, analysis: AnalysisConfig) -> list[Path]:
    """Write ``episodes.csv`` (one row per episode) from the hourly mart, if present.

    The hourly mart is never published, so this runs only where the pipeline built it
    (the Daily ELT); elsewhere it is skipped with a warning.

    Args:
        model_input: Folder with ``fct_pm25_hourly.parquet``.
        reporting: The ``08_reporting`` folder.
        analysis: Window.

    Returns:
        The written files (empty if skipped).
    """
    hourly = model_input / "fct_pm25_hourly.parquet"
    if not hourly.exists():
        logger.warning("episodes skipped: %s not found (hourly data is never published)", hourly)
        return []
    params = {"hourly": str(hourly), "start": analysis.start, "end": analysis.end}
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'America/Bogota'")
        rows = con.execute(MOVING_AVERAGE_SQL, params).fetchall()

    by_station: dict[int, tuple[list[str], list[float | None]]] = {}
    for station, hour, value in rows:
        hours, values = by_station.setdefault(int(station), ([], []))
        hours.append(str(hour))
        values.append(None if value is None else float(value))

    reporting.mkdir(parents=True, exist_ok=True)
    path = reporting / "episodes.csv"
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for station, (hours, values) in sorted(by_station.items()):
            for episode in detect_episodes(values):
                # The grid has every hour, so index differences are hours.
                writer.writerow(
                    (
                        station,
                        episode.level,
                        hours[episode.start],
                        hours[episode.end] if episode.end is not None else None,
                        episode.end - episode.start if episode.end is not None else None,
                        episode.peak,
                    )
                )
                count += 1
    logger.info("episodes stations=%d episodes=%d", len(by_station), count)
    return [path]
