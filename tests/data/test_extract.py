from datetime import date
from pathlib import Path

import httpx
import pytest

from aburra_air.data.extract import ExtractError, extract_siata, land
from tests.conftest import SIATA_FIXTURES, RecordedSiata

RUN_DATE = date(2026, 10, 10)


def day_dir(raw: Path) -> Path:
    return raw / "siata" / "pm25" / "2026-10-10"


def test_lands_stations_and_each_series_unchanged(tmp_path: Path, siata_api: RecordedSiata) -> None:
    with siata_api.client() as client:
        written = extract_siata(client, tmp_path, RUN_DATE)

    folder = day_dir(tmp_path)
    assert sorted(p.name for p in written) == ["12.json", "81.json", "stations.json"]
    assert (folder / "81.json").read_bytes() == (SIATA_FIXTURES / "pm25_72h_81.json").read_bytes()
    assert not list(folder.glob("*.part"))


def test_second_run_same_day_makes_no_requests(tmp_path: Path, siata_api: RecordedSiata) -> None:
    with siata_api.client() as client:
        extract_siata(client, tmp_path, RUN_DATE)
        before = {p: p.read_bytes() for p in day_dir(tmp_path).iterdir()}
        siata_api.requests.clear()
        written = extract_siata(client, tmp_path, RUN_DATE)

    assert written == []
    assert siata_api.requests == []
    assert {p: p.read_bytes() for p in day_dir(tmp_path).iterdir()} == before


def test_one_request_per_station_per_run(tmp_path: Path, siata_api: RecordedSiata) -> None:
    with siata_api.client() as client:
        extract_siata(client, tmp_path, RUN_DATE)
    paths = [r.url.path for r in siata_api.requests]
    assert len(paths) == len(set(paths)) == 3


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(404), httpx.Response(200, content=b"<html>maintenance</html>")],
)
def test_failed_station_is_not_landed_and_retried_next_run(
    tmp_path: Path, siata_api: RecordedSiata, failure: httpx.Response
) -> None:
    siata_api.overrides[12] = failure
    with siata_api.client() as client, pytest.raises(ExtractError, match=r"\[12\]"):
        extract_siata(client, tmp_path, RUN_DATE)
    assert (day_dir(tmp_path) / "81.json").exists()
    assert not (day_dir(tmp_path) / "12.json").exists()

    siata_api.overrides.clear()
    siata_api.requests.clear()
    with siata_api.client() as client:
        written = extract_siata(client, tmp_path, RUN_DATE)
    assert [p.name for p in written] == ["12.json"]
    assert [r.url.path.rsplit("/", 1)[-1] for r in siata_api.requests] == ["12"]


def test_network_failure_after_retries_is_reported(
    tmp_path: Path, siata_api: RecordedSiata
) -> None:
    siata_api.overrides[81] = httpx.ConnectTimeout("timeout")
    with siata_api.client() as client, pytest.raises(ExtractError, match=r"\[81\]"):
        extract_siata(client, tmp_path, RUN_DATE)
    assert (day_dir(tmp_path) / "12.json").exists()


def test_malformed_stations_list_is_not_landed(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"{}"))
    with (
        httpx.Client(transport=transport, base_url="https://x") as client,
        pytest.raises(ValueError, match="stations"),
    ):
        extract_siata(client, tmp_path, RUN_DATE)
    assert not (day_dir(tmp_path) / "stations.json").exists()


def test_land_leaves_no_partial_file_and_replaces_stale_part(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b.json"
    target.parent.mkdir()
    (target.parent / "b.json.part").write_bytes(b"half")  # left by an interrupted run
    land(target, b"{}")
    assert target.read_bytes() == b"{}"
    assert not (target.parent / "b.json.part").exists()
