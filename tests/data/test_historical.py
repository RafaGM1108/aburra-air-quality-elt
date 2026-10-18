from datetime import datetime
from pathlib import Path

import duckdb
import httpx
import pytest

from aburra_air.data.extract import TIMEZONE
from aburra_air.data.historical import (
    HISTORICAL_FILE,
    backfill_siata,
    parse_historical,
    parse_timestamp,
)
from aburra_air.data.load import load_siata
from tests.conftest import SIATA_FIXTURES, RecordedSiata


def test_parse_historical_maps_missing_and_keeps_quality() -> None:
    readings = parse_historical((SIATA_FIXTURES / "historical_pm25.json").read_bytes())
    assert len(readings) == 4
    assert readings[0] == (12, datetime(2023, 7, 31, 0, tzinfo=TIMEZONE), 21.0, "1")
    assert readings[1] == (12, datetime(2023, 7, 31, 1, tzinfo=TIMEZONE), None, "151")


def test_parse_historical_keeps_one_row_per_station_hour() -> None:
    body = b"""[{"codigoSerial": 12, "datos": [
        {"fecha": "2023-07-31 00:00:00", "valor": 1, "calidad": 1},
        {"fecha": "2023-07-31 00:00:00", "valor": 2, "calidad": 1}]}]"""
    assert [r[2] for r in parse_historical(body)] == [2.0]


@pytest.mark.parametrize(
    "body", [b"{}", b"[]", b'[{"codigoSerial": 12}]', b'[{"codigoSerial": 12, "datos": []}]', b"x"]
)
def test_parse_historical_rejects_malformed_body(body: bytes) -> None:
    with pytest.raises(ValueError, match="Unexpected SIATA historical"):
        parse_historical(body)


@pytest.mark.parametrize(
    "value",
    ["2023-07-31 05:00:00", "2023-07-31T05:00:00", "2023-07-31T10:00:00+00:00"],
)
def test_parse_timestamp_returns_bogota_time(value: str) -> None:
    assert parse_timestamp(value) == datetime(2023, 7, 31, 5, tzinfo=TIMEZONE)


def test_backfill_lands_once(tmp_path: Path, siata_api: RecordedSiata) -> None:
    with siata_api.client() as client:
        assert backfill_siata(client, tmp_path) == tmp_path / HISTORICAL_FILE
        siata_api.requests.clear()
        assert backfill_siata(client, tmp_path) is None
    assert siata_api.requests == []


def test_backfill_does_not_land_a_malformed_body(tmp_path: Path, siata_api: RecordedSiata) -> None:
    siata_api.historical = httpx.Response(200, content=b"<html>maintenance</html>")
    with siata_api.client() as client, pytest.raises(ValueError, match="historical"):
        backfill_siata(client, tmp_path)
    assert not (tmp_path / HISTORICAL_FILE).exists()


def test_load_fills_historical_table_idempotently(tmp_path: Path) -> None:
    target = tmp_path / HISTORICAL_FILE
    target.parent.mkdir(parents=True)
    target.write_bytes((SIATA_FIXTURES / "historical_pm25.json").read_bytes())
    with duckdb.connect() as con:
        assert load_siata(tmp_path, con) == 1
        load_siata(tmp_path, con)
        sql = "SELECT count(*), count(pm25), count(DISTINCT station_code) FROM {}"
        assert con.sql(sql.format("raw.siata_pm25_historical")).fetchone() == (4, 3, 2)
