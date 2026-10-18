import os
import time
from datetime import date
from pathlib import Path

import httpx
import pytest

from aburra_air.data import marts as views


def test_ensure_marts_downloads_only_missing_ones(marts: Path) -> None:
    (marts / "dim_stations.parquet").unlink()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, content=b"PAR1")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert views.ensure_marts(marts, client) == marts
    assert requested == ["dim_stations.parquet"]
    assert (marts / "dim_stations.parquet").read_bytes() == b"PAR1"
    assert not list(marts.glob("*.part"))


def test_ensure_marts_refreshes_stale_ones_and_keeps_them_if_offline(marts: Path) -> None:
    stale = marts / "dim_stations.parquet"
    os.utime(stale, (time.time() - 2 * 86400,) * 2)

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        views.ensure_marts(marts, client, max_age_hours=24)
    assert stale.read_bytes().startswith(b"PAR1")  # still the original Parquet

    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"new"))
    ) as client:
        views.ensure_marts(marts, client, max_age_hours=24)
    assert stale.read_bytes() == b"new"
    assert (marts / "fct_pm25_daily.parquet").read_bytes() != b"new"  # fresh, not refetched


def test_ensure_marts_fails_when_a_missing_mart_cannot_be_fetched(marts: Path) -> None:
    (marts / "dim_stations.parquet").unlink()
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        views.ensure_marts(marts, client, max_age_hours=24)


def test_latest_ica_has_located_stations_only(marts: Path) -> None:
    latest = views.latest_ica(marts)
    assert latest["station_code"].tolist() == [1, 2]  # station 3 has no location
    assert latest.loc[0, "pm25_mean"] == 20.0  # station 1's last day (2024-01-10)
    assert latest.loc[0, "ica_category"] == "Aceptable"


def test_station_options_label_known_stations(marts: Path) -> None:
    options = views.station_options(marts)
    assert options["label"].tolist() == ["AAA · Alpha", "BBB · Beta", "CCC · Gamma"]


def test_daily_series_keeps_valid_days(marts: Path) -> None:
    assert len(views.daily_series(marts, 1)) == 10
    assert len(views.daily_series(marts, 3)) == 5
    assert views.daily_series(marts, 999).empty
    january_2nd = (date(2024, 1, 2), date(2024, 1, 2))
    assert views.daily_series(marts, 1, january_2nd)["pm25_mean"].tolist() == [50.0]
    assert views.monthly_exceedances(marts, 1, (date(2024, 2, 1), date(2024, 12, 1))).empty


def test_monthly_and_hour_profile(marts: Path) -> None:
    monthly = views.monthly_exceedances(marts, 1)
    assert monthly["exceedance_days"].tolist() == [4]
    profile = views.hour_profile(marts, 1)
    weekday = profile[profile["day_type"] == "weekday"].set_index("hour_of_day")
    assert weekday.loc[7, "pm25_mean"] == 40.0
    assert views.hour_profile(marts, 2).empty
