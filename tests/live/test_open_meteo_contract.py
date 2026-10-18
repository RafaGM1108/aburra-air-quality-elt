"""Contract check against the live Open-Meteo APIs (run by ``make contract``).

Two small requests, a day each, with the exact variables and parameters the extractor
uses, so a renamed variable fails here instead of in the Daily ELT.
"""

import json
from collections.abc import Iterator

import httpx
import pytest

from aburra_air.data import open_meteo, siata

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client() -> Iterator[httpx.Client]:
    with siata.make_client() as http:
        yield http


def assert_every_variable_has_values(body: bytes) -> None:
    hourly = json.loads(body)["hourly"]
    empty = [name for name in open_meteo.HOURLY if all(v is None for v in hourly[name])]
    assert empty == []


def test_forecast_returns_the_last_full_days(client: httpx.Client) -> None:
    body = open_meteo.fetch(client, open_meteo.FORECAST_URL, past_days=1, forecast_days=0)
    assert open_meteo.check_hourly(body) == 24
    assert_every_variable_has_values(body)


def test_archive_returns_the_historical_year(client: httpx.Client) -> None:
    day = open_meteo.HISTORICAL_START.isoformat()
    body = open_meteo.fetch(client, open_meteo.ARCHIVE_URL, start_date=day, end_date=day)
    assert open_meteo.check_hourly(body) == 24
    assert_every_variable_has_values(body)
