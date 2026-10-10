"""Land SIATA responses in ``01_raw``, incrementally and idempotently.

Layout: ``<raw>/siata/pm25/<run date>/stations.json`` and ``<station code>.json``. A file
that already exists is never fetched or written again, so re-running on the same day
only fills what is missing.
"""

import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from aburra_air.data import siata

TIMEZONE = ZoneInfo("America/Bogota")
LANDING_DIR = Path("siata") / "pm25"

logger = logging.getLogger(__name__)


class ExtractError(RuntimeError):
    """Some stations could not be extracted; the others were landed."""


def today() -> date:
    """Return the current date in Medellín, which names the landing folder."""
    return datetime.now(TIMEZONE).date()


def land(path: Path, body: bytes) -> None:
    """Write a file atomically, so an interrupted run never leaves a partial file.

    Args:
        path: Destination file.
        body: Bytes to write, unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    partial.replace(path)


def extract_siata(client: httpx.Client, raw_dir: Path, run_date: date) -> list[Path]:
    """Land the stations list and each station's 72 h series for one run date.

    Responses are checked before landing, so a malformed body is retried on the next
    run instead of being skipped as already landed.

    Args:
        client: Client from :func:`aburra_air.data.siata.make_client`.
        raw_dir: The ``01_raw`` folder.
        run_date: Date that names the landing folder.

    Returns:
        Files written by this call (empty if everything was already landed).

    Raises:
        ExtractError: If any station failed; the others are landed first.
        httpx.HTTPError: If the stations list cannot be fetched.
        ValueError: If the stations list has an unexpected shape.
    """
    day_dir = raw_dir / LANDING_DIR / run_date.isoformat()
    written: list[Path] = []

    stations_file = day_dir / "stations.json"
    if stations_file.exists():
        codes = siata.station_codes(stations_file.read_bytes())
    else:
        stations = siata.fetch_stations(client)
        codes = siata.station_codes(stations)  # validate before landing
        land(stations_file, stations)
        written.append(stations_file)

    failed: list[int] = []
    for code in codes:
        target = day_dir / f"{code}.json"
        if target.exists():
            logger.info("skip station=%s reason=already_landed", code)
            continue
        try:
            series = siata.fetch_series(client, code)
            siata.check_series(series)
        except (httpx.HTTPError, ValueError) as error:
            logger.error("fail station=%s error=%r", code, error)
            failed.append(code)
            continue
        land(target, series)
        written.append(target)

    logger.info(
        "extract date=%s stations=%d written=%d failed=%d",
        run_date,
        len(codes),
        len(written),
        len(failed),
    )
    if failed:
        raise ExtractError(f"Stations not extracted on {run_date}: {failed}")
    return written
