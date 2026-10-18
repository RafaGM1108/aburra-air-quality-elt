import shutil
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from aburra_air.data.extract import TIMEZONE
from aburra_air.data.load import load_siata
from aburra_air.data.quality import QualityError, check_all
from aburra_air.utils.config import QualityConfig
from tests.conftest import SIATA_FIXTURES

# Fixture series end at 2026-10-10 07:00 local; this is ~7 h later, like a normal run.
NOW = datetime(2026, 10, 10, 14, tzinfo=TIMEZONE)
OK = QualityConfig(max_lag_hours=36, min_rows_latest_run=100, min_stations_last_24h=2)


def build_db(raw: Path, con: duckdb.DuckDBPyConnection) -> None:
    """Load the fixtures and create the staging view and marts the checks read."""
    day = raw / "siata" / "pm25" / "2026-10-10"
    day.mkdir(parents=True)
    for code in (12, 81):
        shutil.copy(SIATA_FIXTURES / f"pm25_72h_{code}.json", day / f"{code}.json")
    load_siata(raw, con)
    con.execute("""
        CREATE SCHEMA staging;
        CREATE VIEW staging.stg_siata__pm25_live AS SELECT * FROM raw.siata_pm25_hourly;
        CREATE SCHEMA marts;
        CREATE TABLE marts.fct_pm25_hourly AS
            SELECT station_code, timestamp_hour FROM raw.siata_pm25_hourly;
        CREATE TABLE marts.fct_pm25_daily AS
            SELECT DISTINCT station_code, timestamp_hour::DATE AS date_local
            FROM raw.siata_pm25_hourly;
    """)


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    build_db(tmp_path, con)
    return con


def test_healthy_run_passes(con: duckdb.DuckDBPyConnection) -> None:
    check_all(con, OK, NOW)


@pytest.mark.parametrize(
    ("quality", "now", "message"),
    [
        (OK, datetime(2026, 10, 12, 14, tzinfo=TIMEZONE), "freshness: latest live hour is 55 h"),
        (OK.model_copy(update={"min_rows_latest_run": 1000}), NOW, "row count: latest run"),
        (OK.model_copy(update={"min_stations_last_24h": 3}), NOW, "station coverage: 2 stations"),
    ],
)
def test_failed_check_fails_with_a_clear_message(
    con: duckdb.DuckDBPyConnection, quality: QualityConfig, now: datetime, message: str
) -> None:
    with pytest.raises(QualityError, match=message):
        check_all(con, quality, now)


def test_duplicate_mart_key_fails(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSERT INTO marts.fct_pm25_hourly SELECT * FROM marts.fct_pm25_hourly LIMIT 1")
    with pytest.raises(QualityError, match="duplicates: 1 repeated keys"):
        check_all(con, OK, NOW)


def test_every_failure_is_reported_at_once(con: duckdb.DuckDBPyConnection) -> None:
    strict = QualityConfig(max_lag_hours=1, min_rows_latest_run=1000, min_stations_last_24h=3)
    with pytest.raises(QualityError) as error:
        check_all(con, strict, NOW)
    assert str(error.value).count("\n- ") == 3


def test_nothing_loaded_fails_freshness(tmp_path: Path) -> None:
    with duckdb.connect() as con:
        load_siata(tmp_path, con)
        with pytest.raises(QualityError, match="no live readings loaded") as error:
            check_all(con, OK, NOW)
    assert "check_station_coverage: Catalog Error" in str(error.value)
