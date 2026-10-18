"""Load landed SIATA responses from ``01_raw`` into DuckDB raw tables.

Every run reloads all landed files and upserts them, so loading twice changes nothing.
Run folders are read oldest first: when two runs overlap on ``(station_code,
timestamp_hour)`` the newer value wins, but a newer ``null`` never erases a value.
The historical backfill file, if landed, goes to its own table with SIATA's quality flag.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

from aburra_air.data.extract import LANDING_DIR, TIMEZONE
from aburra_air.data.historical import HISTORICAL_FILE, parse_historical

logger = logging.getLogger(__name__)

Reading = tuple[int, datetime, float | None]
Station = tuple[int, str, str, str, float, float]

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.siata_pm25_hourly (
    station_code INTEGER NOT NULL,
    timestamp_hour TIMESTAMPTZ NOT NULL,
    pm25 DOUBLE,
    landed_on DATE NOT NULL,
    PRIMARY KEY (station_code, timestamp_hour)
);
CREATE TABLE IF NOT EXISTS raw.siata_pm25_historical (
    station_code INTEGER NOT NULL,
    timestamp_hour TIMESTAMPTZ NOT NULL,
    pm25 DOUBLE,
    quality VARCHAR,
    PRIMARY KEY (station_code, timestamp_hour)
);
CREATE TABLE IF NOT EXISTS raw.siata_stations (
    station_code INTEGER PRIMARY KEY,
    station_id VARCHAR NOT NULL,
    station_name VARCHAR NOT NULL,
    municipality VARCHAR NOT NULL,
    longitude DOUBLE NOT NULL,
    latitude DOUBLE NOT NULL,
    landed_on DATE NOT NULL
);
"""

# Whole columns are bound as lists: one statement per file, ~100x faster than executemany.
UPSERT_READINGS = """
INSERT INTO raw.siata_pm25_hourly
SELECT unnest($code::INTEGER[]), unnest($hour::TIMESTAMPTZ[]), unnest($pm25::DOUBLE[]),
    $landed_on::DATE
ON CONFLICT (station_code, timestamp_hour) DO UPDATE SET
    pm25 = COALESCE(excluded.pm25, pm25),
    landed_on = excluded.landed_on
"""

UPSERT_HISTORICAL = """
INSERT OR REPLACE INTO raw.siata_pm25_historical
SELECT unnest($code::INTEGER[]), unnest($hour::TIMESTAMPTZ[]), unnest($pm25::DOUBLE[]),
    unnest($quality::VARCHAR[])
"""

UPSERT_STATION = """
INSERT OR REPLACE INTO raw.siata_stations VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def parse_series(body: bytes, code: int) -> list[Reading]:
    """Turn a 72 h series response into hourly readings with their local timestamp.

    Only the last hour (``Hora_fin``) is given; each value's hour is counted back from
    it and checked against ``Horas``.

    Args:
        body: A landed ``<station code>.json`` file.
        code: The station code the file was landed for.

    Returns:
        ``(station_code, timestamp_hour, pm25)`` rows; ``pm25`` is ``None`` when missing.

    Raises:
        ValueError: If the body is malformed or ``Horas`` disagrees with ``Hora_fin``.
    """
    try:
        info = json.loads(body)["info"]
        end = datetime.strptime(info["Hora_fin"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE)
        pairs = list(zip(info["Horas"], info["PM25_72H"], strict=True))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected SIATA series for station {code}: {error!r}") from error

    readings: list[Reading] = []
    for position, (hour, value) in enumerate(pairs):
        timestamp = end - timedelta(hours=len(pairs) - 1 - position)
        if timestamp.hour != hour:
            raise ValueError(f"Station {code}: hour {hour} at {timestamp} does not match Hora_fin")
        readings.append((code, timestamp, None if value is None else float(value)))
    return readings


def parse_stations(body: bytes) -> list[Station]:
    """Read station metadata from a stations response.

    Args:
        body: A landed ``stations.json`` file.

    Returns:
        ``(station_code, station_id, station_name, municipality, longitude, latitude)``.

    Raises:
        ValueError: If the body is not the expected GeoJSON shape.
    """
    try:
        stations: list[Station] = []
        for feature in json.loads(body)["features"]:
            props = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"]
            stations.append(
                (
                    int(props["codigo"]),
                    str(props["estacion"]),
                    str(props["nombreEstacion"]),
                    str(props["Municipio"]),
                    float(longitude),
                    float(latitude),
                )
            )
        return stations
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected SIATA stations response: {error!r}") from error


def columns(rows: list[tuple[object, ...]], names: tuple[str, ...]) -> dict[str, list[object]]:
    """Turn rows into one list per column, named for the bulk upsert parameters.

    Args:
        rows: Tuples with one value per name.
        names: Parameter names, in tuple order.

    Returns:
        ``{name: [values]}``; empty lists if there are no rows.
    """
    return {name: [row[i] for row in rows] for i, name in enumerate(names)}


def load_historical(raw_dir: Path, con: duckdb.DuckDBPyConnection) -> int:
    """Upsert the landed historical file into ``raw.siata_pm25_historical``, if present.

    Args:
        raw_dir: The ``01_raw`` folder.
        con: Open DuckDB connection with the raw schema created.

    Returns:
        Number of readings loaded (0 if the file is not landed).

    Raises:
        ValueError: If the file is malformed.
    """
    path = raw_dir / HISTORICAL_FILE
    if not path.exists():
        return 0
    readings: list[tuple[object, ...]] = list(parse_historical(path.read_bytes()))
    con.execute(UPSERT_HISTORICAL, columns(readings, ("code", "hour", "pm25", "quality")))
    logger.info("load historical readings=%d", len(readings))
    return len(readings)


def load_siata(raw_dir: Path, con: duckdb.DuckDBPyConnection) -> int:
    """Upsert every landed SIATA file into the ``raw`` schema.

    Live series go to ``siata_pm25_hourly``, station lists to ``siata_stations`` and the
    historical backfill file to ``siata_pm25_historical``.

    Args:
        raw_dir: The ``01_raw`` folder.
        con: Open DuckDB connection; tables are created if missing.

    Returns:
        Number of files loaded.

    Raises:
        ValueError: If a landed file is malformed; nothing from its run folder is committed.
    """
    con.execute(SCHEMA)
    files = 0
    for day_dir in sorted(p for p in (raw_dir / LANDING_DIR).glob("*") if p.is_dir()):
        landed_on = date.fromisoformat(day_dir.name)
        day_files = sorted(day_dir.glob("*.json"))
        con.begin()
        try:
            for path in day_files:
                body = path.read_bytes()
                if path.stem == "stations":
                    rows: list[tuple[object, ...]] = [(*s, landed_on) for s in parse_stations(body)]
                    con.executemany(UPSERT_STATION, rows)
                else:
                    rows = list(parse_series(body, int(path.stem)))
                    params = columns(rows, ("code", "hour", "pm25"))
                    con.execute(UPSERT_READINGS, {**params, "landed_on": landed_on})
        except Exception:
            con.rollback()
            raise
        con.commit()
        files += len(day_files)
        logger.info("load date=%s files=%d", landed_on, len(day_files))
    if load_historical(raw_dir, con):
        files += 1
    return files
