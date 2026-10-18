"""One-off backfill from SIATA's frozen ``EntregaData1`` PM2.5 file (2023-07 → 2024-07).

The file stopped updating in 2024-08 (see ``docs/data.md``), so it is landed once in
``<raw>/siata/historical/pm25.json`` and never fetched again.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from aburra_air.data import siata
from aburra_air.data.extract import TIMEZONE, land

HISTORICAL_URL = "https://siata.gov.co/EntregaData1/Datos_SIATA_Aire_pm25.json"
HISTORICAL_FILE = Path("siata") / "historical" / "pm25.json"
MISSING = -9999

HistoricalReading = tuple[int, datetime, float | None, str | None]

logger = logging.getLogger(__name__)


def parse_timestamp(value: str) -> datetime:
    """Parse a ``fecha`` value as America/Bogota time, keeping an explicit offset if any.

    Args:
        value: ISO-like date and time, e.g. ``2023-07-31 00:00:00``.

    Returns:
        A timezone-aware datetime in America/Bogota.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TIMEZONE)
    return parsed.astimezone(TIMEZONE)


def parse_historical(body: bytes) -> list[HistoricalReading]:
    """Read hourly readings from the historical file.

    Args:
        body: The ``Datos_SIATA_Aire_pm25.json`` body.

    Returns:
        ``(station_code, timestamp_hour, pm25, quality)`` rows, one per station and
        hour (the last one wins on duplicates); ``pm25`` is ``None`` for ``-9999``.

    Raises:
        ValueError: If the body is not the expected shape or has no readings.
    """
    readings: dict[tuple[int, datetime], HistoricalReading] = {}
    try:
        stations = json.loads(body)
        if not isinstance(stations, list):
            raise TypeError(f"expected a list of stations, got {type(stations).__name__}")
        for station in stations:
            code = int(station["codigoSerial"])
            for row in station["datos"]:
                hour = parse_timestamp(str(row["fecha"]))
                value = float(row["valor"])
                quality = None if row.get("calidad") is None else str(row["calidad"])
                readings[code, hour] = (code, hour, None if value == MISSING else value, quality)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected SIATA historical file: {error!r}") from error
    if not readings:
        raise ValueError("Unexpected SIATA historical file: no readings")
    return list(readings.values())


def backfill_siata(client: httpx.Client, raw_dir: Path) -> Path | None:
    """Land the historical PM2.5 file once; later calls make no request.

    Args:
        client: Client from :func:`aburra_air.data.siata.make_client`.
        raw_dir: The ``01_raw`` folder.

    Returns:
        The landed file, or ``None`` if it was already landed.

    Raises:
        httpx.HTTPError: If the file cannot be fetched.
        ValueError: If the body is malformed; nothing is landed.
    """
    target = raw_dir / HISTORICAL_FILE
    if target.exists():
        logger.info("skip historical reason=already_landed")
        return None
    body = siata.get(client, HISTORICAL_URL)
    readings = parse_historical(body)  # validate before landing
    land(target, body)
    logger.info("backfill readings=%d file=%s", len(readings), target)
    return target
