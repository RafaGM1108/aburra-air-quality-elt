from pathlib import Path

import httpx
import pytest

from aburra_air.data import siata

SIATA_FIXTURES = Path(__file__).parent / "fixtures" / "siata"


class RecordedSiata:
    """Serves responses recorded from the SIATA geoportal; records every request.

    ``overrides`` maps a station code to the response (or exception) to return instead.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.overrides: dict[int, httpx.Response | Exception] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith(siata.STATIONS_PATH):
            return httpx.Response(200, content=(SIATA_FIXTURES / "pm25_stations.json").read_bytes())
        code = int(request.url.path.rsplit("/", 1)[-1])
        override = self.overrides.get(code)
        if isinstance(override, Exception):
            raise override
        if override is not None:
            return override
        return httpx.Response(200, content=(SIATA_FIXTURES / f"pm25_72h_{code}.json").read_bytes())

    def client(self) -> httpx.Client:
        return siata.make_client(httpx.MockTransport(self))


@pytest.fixture
def siata_api() -> RecordedSiata:
    return RecordedSiata()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(siata.get.retry, "sleep", lambda _: None)
