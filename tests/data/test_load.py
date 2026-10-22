import shutil
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from aburra_air.data.extract import TIMEZONE
from aburra_air.data.load import (
    load_open_meteo,
    load_siata,
    parse_open_meteo,
    parse_series,
    parse_stations,
)
from tests.conftest import OPEN_METEO_FIXTURE, SIATA_FIXTURES


def land_fixtures(raw: Path, run_date: str) -> Path:
    day = raw / "siata" / "pm25" / run_date
    day.mkdir(parents=True)
    shutil.copy(SIATA_FIXTURES / "pm25_stations.json", day / "stations.json")
    for code in (12, 81):
        shutil.copy(SIATA_FIXTURES / f"pm25_72h_{code}.json", day / f"{code}.json")
    return day


def test_parse_series_counts_hours_back_from_hora_fin() -> None:
    readings = parse_series((SIATA_FIXTURES / "pm25_72h_12.json").read_bytes(), 12)
    assert len(readings) == 72
    assert readings[-1] == (12, datetime(2026, 10, 10, 7, tzinfo=TIMEZONE), 49.0)
    assert readings[0][1] == datetime(2026, 10, 7, 8, tzinfo=TIMEZONE)
    assert any(value is None for _, _, value in readings)


def test_parse_series_rejects_hours_that_disagree_with_hora_fin() -> None:
    body = b'{"info": {"Hora_fin": "2026-10-10 07:00:00", "Horas": [6, 8], "PM25_72H": [1.0, 2.0]}}'
    with pytest.raises(ValueError, match="does not match"):
        parse_series(body, 12)


@pytest.mark.parametrize("body", [b"<html></html>", b'{"info": {}}'])
def test_parse_series_rejects_malformed_body(body: bytes) -> None:
    with pytest.raises(ValueError, match="Unexpected SIATA series"):
        parse_series(body, 12)


def test_parse_stations_reads_metadata() -> None:
    stations = parse_stations((SIATA_FIXTURES / "pm25_stations.json").read_bytes())
    assert stations[0] == (81, "BAR-TORR", "Torre Social", "Barbosa", -75.330399, 6.43696)


def test_parse_stations_rejects_malformed_body() -> None:
    with pytest.raises(ValueError, match="Unexpected SIATA stations"):
        parse_stations(b'{"features": [{"properties": {}}]}')


def test_load_siata_fills_raw_tables(tmp_path: Path) -> None:
    land_fixtures(tmp_path, "2026-10-10")
    with duckdb.connect() as con:
        assert load_siata(tmp_path, con) == 3
        hourly = con.sql("SELECT count(*), count(DISTINCT station_code) FROM raw.siata_pm25_hourly")
        assert hourly.fetchone() == (144, 2)
        expected = len(parse_stations((SIATA_FIXTURES / "pm25_stations.json").read_bytes()))
        assert con.sql("SELECT count(*) FROM raw.siata_stations").fetchone() == (expected,)


def test_load_siata_with_nothing_landed(tmp_path: Path) -> None:
    with duckdb.connect() as con:
        assert load_siata(tmp_path, con) == 0
        assert con.sql("SELECT count(*) FROM raw.siata_pm25_hourly").fetchone() == (0,)


def test_parse_open_meteo_keeps_local_time_and_missing_values() -> None:
    readings = parse_open_meteo(OPEN_METEO_FIXTURE.read_bytes())
    assert readings[0] == (
        datetime(2024, 1, 1, tzinfo=TIMEZONE),
        17.2,
        88.0,
        0.0,
        3.1,
        140.0,
        210.0,
    )
    assert readings[-1][1] is None


def test_load_open_meteo_uses_newer_daily_landing_for_overlaps(tmp_path: Path) -> None:
    daily = tmp_path / "open_meteo" / "hourly"
    daily.mkdir(parents=True)
    first = OPEN_METEO_FIXTURE.read_text().replace(
        '"temperature_2m": [17.2, 16.8, null]', '"temperature_2m": [17.2, 16.8, 15.0]'
    )
    second = first.replace(
        '"temperature_2m": [17.2, 16.8, 15.0]', '"temperature_2m": [21.0, 16.8, 15.0]'
    )
    (daily / "2024-01-02.json").write_text(first)
    (daily / "2024-01-03.json").write_text(second)

    with duckdb.connect() as con:
        assert load_open_meteo(tmp_path, con) == 2
        rows = con.sql(
            "SELECT count(*), min(temperature_2m), max(temperature_2m) FROM raw.open_meteo_hourly"
        ).fetchone()
    assert rows == (3, 15.0, 21.0)
