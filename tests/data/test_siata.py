import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from aburra_air.data import siata

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "siata"


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return siata.make_client(httpx.MockTransport(handler))


def recorded(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith(siata.STATIONS_PATH):
        return httpx.Response(200, content=(FIXTURES / "pm25_stations.json").read_bytes())
    code = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(200, content=(FIXTURES / f"pm25_72h_{code}.json").read_bytes())


def test_fetch_returns_body_unchanged_and_sends_user_agent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return recorded(request)

    with client_for(handler) as client:
        stations = siata.fetch_stations(client)
        series = siata.fetch_series(client, 81)
    assert stations == (FIXTURES / "pm25_stations.json").read_bytes()
    assert series == (FIXTURES / "pm25_72h_81.json").read_bytes()
    assert {r.headers["user-agent"] for r in seen} == {siata.USER_AGENT}
    assert str(seen[1].url) == f"{siata.BASE_URL}/geographJson/1/pm25/81"


def test_station_codes_from_recorded_response() -> None:
    assert siata.station_codes((FIXTURES / "pm25_stations.json").read_bytes()) == [81, 12]


@pytest.mark.parametrize("body", [b"not json", b"{}", b'{"features": [{"properties": {}}]}'])
def test_station_codes_rejects_unexpected_shape(body: bytes) -> None:
    with pytest.raises(ValueError, match="Unexpected SIATA stations response"):
        siata.station_codes(body)


def test_check_series_accepts_recorded_response() -> None:
    siata.check_series((FIXTURES / "pm25_72h_12.json").read_bytes())


@pytest.mark.parametrize(
    "body",
    [
        b"<html>error</html>",
        b'{"detail": "Not Found"}',
        b'{"info": {"Hora_fin": "2026-10-10 07:00:00", "Horas": [1, 2], "PM25_72H": [3.0]}}',
        b'{"info": {"Hora_fin": "", "Horas": [], "PM25_72H": []}}',
    ],
)
def test_check_series_rejects_unexpected_shape(body: bytes) -> None:
    with pytest.raises(ValueError, match="Unexpected SIATA series response"):
        siata.check_series(body)


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.Response(429), httpx.ConnectTimeout("timeout")],
)
def test_transient_errors_are_retried(failure: httpx.Response | Exception) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            if isinstance(failure, Exception):
                raise failure
            return failure
        return recorded(request)

    with client_for(handler) as client:
        assert json.loads(siata.fetch_series(client, 12))["info"]["Codigo"] == 12
    assert calls == 3


def test_client_errors_are_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    with client_for(handler) as client, pytest.raises(httpx.HTTPStatusError):
        siata.fetch_series(client, 999)
    assert calls == 1


def test_gives_up_after_max_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with client_for(handler) as client, pytest.raises(httpx.HTTPStatusError):
        siata.fetch_stations(client)
    assert calls == siata.MAX_ATTEMPTS
