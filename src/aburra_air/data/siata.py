"""Client for the SIATA geoportal API (PM2.5).

The endpoints are undocumented; see ``docs/data.md``. Responses are returned as the raw
bytes received so the extract step can land them unchanged.
"""

import json
import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

BASE_URL = "https://geoportal.siata.gov.co/fastgeoapi/geodata"
STATIONS_PATH = "/geodataJson/1/pm25_minio"
SERIES_PATH = "/geographJson/1/pm25/{code}"
USER_AGENT = "aburra-air-quality-elt/1.0 (+https://github.com/RafaGM1108/aburra-air-quality-elt)"
TIMEOUT_S = 30.0
MAX_ATTEMPTS = 5

logger = logging.getLogger(__name__)


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Create an HTTP client for the SIATA geoportal.

    Args:
        transport: Optional transport, used by tests to serve recorded responses.

    Returns:
        A client with the base URL, timeout and identifying User-Agent set.
    """
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_S,
        transport=transport,
    )


def is_transient(error: BaseException) -> bool:
    """Tell whether a request error is worth retrying.

    Network errors and timeouts, 429 and 5xx responses are transient; other 4xx are not,
    because repeating the same request would fail the same way.

    Args:
        error: The exception raised by the request.

    Returns:
        True if the request should be retried.
    """
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return isinstance(error, httpx.TransportError)


@retry(
    retry=retry_if_exception(is_transient),
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=2, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def get(client: httpx.Client, path: str) -> bytes:
    """GET a path and return the body, retrying transient errors with backoff.

    Args:
        client: Client from :func:`make_client`.
        path: Path relative to :data:`BASE_URL`.

    Returns:
        The response body exactly as received.

    Raises:
        httpx.HTTPStatusError: On a non-2xx response, after retries if transient.
        httpx.TransportError: On a network error that persists after retries.
    """
    response = client.get(path)
    logger.info("GET path=%s status=%s bytes=%d", path, response.status_code, len(response.content))
    response.raise_for_status()
    return response.content


def fetch_stations(client: httpx.Client) -> bytes:
    """Fetch the GeoJSON list of official PM2.5 stations with their last 24 h mean.

    Args:
        client: Client from :func:`make_client`.

    Returns:
        The raw GeoJSON body.
    """
    return get(client, STATIONS_PATH)


def fetch_series(client: httpx.Client, code: int) -> bytes:
    """Fetch the last 72 hourly PM2.5 values of one station.

    Args:
        client: Client from :func:`make_client`.
        code: SIATA station code (``codigo``).

    Returns:
        The raw JSON body.
    """
    return get(client, SERIES_PATH.format(code=code))


def station_codes(stations: bytes) -> list[int]:
    """Read the station codes from a stations response.

    Args:
        stations: Body returned by :func:`fetch_stations`.

    Returns:
        Station codes, in response order.

    Raises:
        ValueError: If the body is not the expected GeoJSON shape.
    """
    try:
        features = json.loads(stations)["features"]
        return [int(feature["properties"]["codigo"]) for feature in features]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected SIATA stations response: {error!r}") from error


def check_series(series: bytes) -> None:
    """Check that a series response has the fields the load step needs.

    A 200 response can still carry an error page or an empty body; landing it would make
    the idempotent extract skip that station for the rest of the day.

    Args:
        series: Body returned by :func:`fetch_series`.

    Raises:
        ValueError: If the body is not the expected shape.
    """
    try:
        info = json.loads(series)["info"]
        if len(info["Horas"]) != len(info["PM25_72H"]) or not info["Hora_fin"]:
            raise ValueError("Horas and PM25_72H differ in length or Hora_fin is empty")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Unexpected SIATA series response: {error!r}") from error
