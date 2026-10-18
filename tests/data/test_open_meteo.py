from datetime import date
from pathlib import Path

import httpx
import pytest

from aburra_air.data import open_meteo
from aburra_air.data.open_meteo import check_hourly, extract_open_meteo
from tests.conftest import OPEN_METEO_FIXTURE, RecordedSiata

RUN_DATE = date(2026, 10, 10)
DAILY = Path("open_meteo") / "hourly" / "2026-10-10.json"


def test_lands_last_days_and_historical_year_unchanged(
    tmp_path: Path, siata_api: RecordedSiata
) -> None:
    with siata_api.client() as client:
        written = extract_open_meteo(client, tmp_path, RUN_DATE)

    assert written == [tmp_path / DAILY, tmp_path / open_meteo.HISTORICAL_FILE]
    assert (tmp_path / DAILY).read_bytes() == OPEN_METEO_FIXTURE.read_bytes()
    forecast, archive = (r.url for r in siata_api.requests)
    assert forecast.host == "api.open-meteo.com"
    assert forecast.params["past_days"] == "3"
    assert forecast.params["forecast_days"] == "0"
    assert forecast.params["timezone"] == "America/Bogota"
    assert forecast.params["hourly"].split(",") == list(open_meteo.HOURLY)
    assert archive.host == "archive-api.open-meteo.com"
    assert (archive.params["start_date"], archive.params["end_date"]) == (
        "2023-07-31",
        "2024-07-31",
    )


def test_second_run_same_day_makes_no_requests(tmp_path: Path, siata_api: RecordedSiata) -> None:
    with siata_api.client() as client:
        extract_open_meteo(client, tmp_path, RUN_DATE)
        siata_api.requests.clear()
        assert extract_open_meteo(client, tmp_path, RUN_DATE) == []
        assert siata_api.requests == []
        # The next day lands a new daily file; the historical year is never fetched again.
        assert extract_open_meteo(client, tmp_path, date(2026, 10, 11)) == [
            tmp_path / "open_meteo" / "hourly" / "2026-10-11.json"
        ]
    assert len(siata_api.requests) == 1


def test_error_response_is_not_landed(tmp_path: Path) -> None:
    error = httpx.Response(400, json={"error": True, "reason": "Cannot initialize"})
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: error)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        extract_open_meteo(client, tmp_path, RUN_DATE)
    assert not (tmp_path / "open_meteo").exists()


@pytest.mark.parametrize(
    "body",
    [
        b"<html>maintenance</html>",
        b'{"hourly": {"time": []}}',
        b'{"hourly": {"time": ["2024-01-01T00:00"], "temperature_2m": [1.0]}}',
    ],
)
def test_check_hourly_rejects_malformed_bodies(body: bytes) -> None:
    with pytest.raises(ValueError, match="Unexpected Open-Meteo response"):
        check_hourly(body)


def test_check_hourly_counts_hours() -> None:
    assert check_hourly(OPEN_METEO_FIXTURE.read_bytes()) == 3
