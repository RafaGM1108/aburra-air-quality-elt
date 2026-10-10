"""Contract check against the live SIATA geoportal (undocumented API, may change).

Excluded from the default test run; ``make contract`` and the weekly workflow run it.
Kept to the stations list plus a few series to stay well under one request per station.
"""

import json
from collections.abc import Iterator
from datetime import datetime

import httpx
import pytest

from aburra_air.data import siata

pytestmark = pytest.mark.live
SAMPLE = 3


@pytest.fixture(scope="module")
def client() -> Iterator[httpx.Client]:
    with siata.make_client() as http:
        yield http


@pytest.fixture(scope="module")
def stations(client: httpx.Client) -> bytes:
    return siata.fetch_stations(client)


def test_stations_list_has_codes(stations: bytes) -> None:
    codes = siata.station_codes(stations)
    assert len(codes) >= 10, f"only {len(codes)} stations listed"
    assert len(set(codes)) == len(codes), "duplicate station codes"


def test_stations_have_name_and_coordinates(stations: bytes) -> None:
    for feature in json.loads(stations)["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        assert -76.0 < lon < -75.0, feature["properties"]["codigo"]
        assert 6.0 < lat < 6.6, feature["properties"]["codigo"]
        assert feature["properties"]["estacion"]


def test_series_shape(client: httpx.Client, stations: bytes) -> None:
    for code in siata.station_codes(stations)[:SAMPLE]:
        body = siata.fetch_series(client, code)
        siata.check_series(body)
        info = json.loads(body)["info"]
        end = datetime.strptime(info["Hora_fin"], "%Y-%m-%d %H:%M:%S")
        assert info["Codigo"] == code
        assert len(info["PM25_72H"]) == 72
        assert info["Horas"][-1] == end.hour, "Horas no longer ends at Hora_fin"
        assert all(v is None or isinstance(v, int | float) for v in info["PM25_72H"])
