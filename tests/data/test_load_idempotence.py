import json
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from aburra_air.data.extract import TIMEZONE
from aburra_air.data.load import load_siata

TABLE = "SELECT station_code, timestamp_hour::VARCHAR, pm25 FROM raw.siata_pm25_hourly ORDER BY ALL"


def land_series(raw: Path, run_date: str, end: str, values: list[float | None]) -> Path:
    """Land a station-12 series ending at ``end`` (local time) under ``run_date``."""
    last = datetime.fromisoformat(end)
    hours = [(last - timedelta(hours=len(values) - 1 - i)).hour for i in range(len(values))]
    body = {
        "info": {"Hora_fin": last.strftime("%Y-%m-%d %H:%M:%S"), "Horas": hours, "PM25_72H": values}
    }
    path = raw / "siata" / "pm25" / run_date / "12.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))
    return path


def pm25_at(con: duckdb.DuckDBPyConnection, local_hour: str) -> object:
    hour = datetime.fromisoformat(local_hour).replace(tzinfo=TIMEZONE)
    sql = "SELECT pm25 FROM raw.siata_pm25_hourly WHERE timestamp_hour = ?"
    row = con.execute(sql, [hour]).fetchone()
    assert row is not None
    return row[0]


def test_loading_twice_changes_nothing(tmp_path: Path) -> None:
    land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [float(v) for v in range(72)])
    with duckdb.connect() as con:
        load_siata(tmp_path, con)
        first = con.sql(TABLE).fetchall()
        load_siata(tmp_path, con)
        assert con.sql(TABLE).fetchall() == first


def test_overlapping_runs_keep_one_row_per_hour_and_newer_value_wins(tmp_path: Path) -> None:
    land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [1.0] * 72)
    land_series(tmp_path, "2026-10-11", "2026-10-11 07:00", [2.0] * 72)
    with duckdb.connect() as con:
        load_siata(tmp_path, con)
        assert con.sql("SELECT count(*) FROM raw.siata_pm25_hourly").fetchone() == (96,)
        assert pm25_at(con, "2026-10-07 08:00") == 1.0  # only in the older run
        assert pm25_at(con, "2026-10-10 07:00") == 2.0  # in both, newer wins


def test_newer_null_never_erases_a_value(tmp_path: Path) -> None:
    land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [5.0] * 72)
    land_series(tmp_path, "2026-10-11", "2026-10-10 07:00", [None] * 72)
    with duckdb.connect() as con:
        load_siata(tmp_path, con)
        assert pm25_at(con, "2026-10-10 07:00") == 5.0


def test_malformed_file_rolls_back_its_folder_only(tmp_path: Path) -> None:
    land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [1.0] * 72)
    land_series(tmp_path, "2026-10-11", "2026-10-11 07:00", [2.0] * 72)
    (tmp_path / "siata" / "pm25" / "2026-10-11" / "81.json").write_text("<html></html>")
    with duckdb.connect() as con:
        with pytest.raises(ValueError, match="station 81"):
            load_siata(tmp_path, con)
        assert con.sql("SELECT count(*), max(pm25) FROM raw.siata_pm25_hourly").fetchone() == (
            72,
            1.0,
        )


def test_partial_files_are_ignored(tmp_path: Path) -> None:
    path = land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [1.0] * 72)
    path.with_name("81.json.part").write_text("{")
    with duckdb.connect() as con:
        assert load_siata(tmp_path, con) == 1


def test_timestamps_keep_the_bogota_offset(tmp_path: Path) -> None:
    land_series(tmp_path, "2026-10-10", "2026-10-10 07:00", [1.0])
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'America/Bogota'")
        load_siata(tmp_path, con)
        row = con.sql(
            "SELECT strftime(timestamp_hour, '%Y-%m-%d %H:%M %z') FROM raw.siata_pm25_hourly"
        )
        assert row.fetchone() == ("2026-10-10 07:00 -05",)
