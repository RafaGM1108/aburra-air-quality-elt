"""Land hourly weather covariates for the valley from Open-Meteo in ``01_raw``.

One grid point on the valley floor (Medellín), the variables in :data:`HOURLY`, hours in
America/Bogota. Each daily run lands the last three full days from the forecast API
(``open_meteo/hourly/<run date>.json``); the historical year is landed once from the
archive API (``open_meteo/historical/hourly.json``). As with SIATA, a landed file is
never fetched again. Data by Open-Meteo.com, CC BY 4.0 (see ``docs/data.md``).
"""

import json
import logging
from datetime import date
from pathlib import Path

import httpx

from aburra_air.data import siata
from aburra_air.data.extract import land

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "boundary_layer_height",
)
LOCATION = {"latitude": 6.2518, "longitude": -75.5636, "timezone": "America/Bogota"}
# The SIATA historical file covers 2023-07-31 to 2024-07-31 (docs/data.md).
HISTORICAL_START = date(2023, 7, 31)
HISTORICAL_END = date(2024, 7, 31)
DAILY_DIR = Path("open_meteo") / "hourly"
HISTORICAL_FILE = Path("open_meteo") / "historical" / "hourly.json"

logger = logging.getLogger(__name__)


def check_hourly(body: bytes) -> int:
    """Check that a response has every variable in :data:`HOURLY` for every hour.

    Args:
        body: Open-Meteo JSON response.

    Returns:
        Number of hours.

    Raises:
        ValueError: If the body is an error or lacks a variable or hours.
    """
    try:
        hourly = json.loads(body)["hourly"]
        hours = len(hourly["time"])
        if not hours or any(len(hourly[name]) != hours for name in HOURLY):
            raise ValueError("no hours, or a variable has a different length than time")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected Open-Meteo response: {error!r}") from error
    return hours


def fetch(client: httpx.Client, url: str, **params: str | int) -> bytes:
    """GET hourly weather at :data:`LOCATION`, retrying like the SIATA client.

    Args:
        client: Client from :func:`aburra_air.data.siata.make_client`.
        url: :data:`FORECAST_URL` or :data:`ARCHIVE_URL`.
        **params: Time-range parameters of that API.

    Returns:
        The raw JSON body.
    """
    query = {**LOCATION, "hourly": ",".join(HOURLY), **params}
    return siata.get(client, str(httpx.URL(url, params=query)))


def extract_open_meteo(client: httpx.Client, raw_dir: Path, run_date: date) -> list[Path]:
    """Land the last three full days of hourly weather, and the historical year once.

    Args:
        client: Client from :func:`aburra_air.data.siata.make_client`.
        raw_dir: The ``01_raw`` folder.
        run_date: Date that names the landing file.

    Returns:
        Files written by this call (empty if both were already landed).

    Raises:
        httpx.HTTPError: If a request fails after retries.
        ValueError: If a response is malformed; it is not landed.
    """
    requests: dict[Path, tuple[str, dict[str, str | int]]] = {
        raw_dir / DAILY_DIR / f"{run_date.isoformat()}.json": (
            FORECAST_URL,
            {"past_days": 3, "forecast_days": 0},
        ),
        raw_dir / HISTORICAL_FILE: (
            ARCHIVE_URL,
            {"start_date": HISTORICAL_START.isoformat(), "end_date": HISTORICAL_END.isoformat()},
        ),
    }
    written: list[Path] = []
    for target, (url, params) in requests.items():
        if target.exists():
            logger.info("skip weather=%s reason=already_landed", target.name)
            continue
        body = fetch(client, url, **params)
        hours = check_hourly(body)
        land(target, body)
        written.append(target)
        logger.info("weather file=%s hours=%d", target, hours)
    return written
