import csv
from pathlib import Path

import duckdb

from aburra_air.analysis.ranking import station_ranking
from tests.conftest import ANALYSIS


def test_ranks_by_exceedance_days_and_leaves_low_coverage_unranked(
    marts: Path, tmp_path: Path
) -> None:
    table, chart = station_ranking(marts, tmp_path / "reporting", ANALYSIS)
    rows = list(csv.DictReader(table.open(encoding="utf-8")))
    assert [(r["rank"], r["station_id"]) for r in rows] == [("1", "AAA"), ("2", "BBB"), ("", "CCC")]
    assert rows[0]["exceedance_days"] == "4"
    assert rows[0]["pm25_mean"] == "32.0"
    assert rows[0]["exceedance_pct"] == "40.0"
    assert rows[2]["coverage"] == "0.5"
    assert chart.stat().st_size > 0


def test_window_excludes_days_outside_it(marts: Path, tmp_path: Path) -> None:
    short = ANALYSIS.model_copy(update={"end": ANALYSIS.start})  # only 2024-01-01
    table, _ = station_ranking(marts, tmp_path / "reporting", short)
    rows = {r["station_id"]: r for r in csv.DictReader(table.open(encoding="utf-8"))}
    assert rows["BBB"]["exceedance_days"] == "1"
    assert rows["CCC"]["valid_days"] == "1"


def test_ties_break_on_unrounded_mean_then_station_code(tmp_path: Path) -> None:
    folder = tmp_path / "marts"
    folder.mkdir()
    # Stations 7 and 5: same exceedances and same rounded mean (20.0), 7 slightly higher.
    # Stations 9 and 8: identical in everything, so the lower code ranks first.
    with duckdb.connect() as con:
        con.execute(f"""
            COPY (SELECT * FROM (VALUES
                (7, DATE '2024-01-01', true, 20.04, false),
                (5, DATE '2024-01-01', true, 20.01, false),
                (9, DATE '2024-01-01', true, 10.0, false),
                (8, DATE '2024-01-01', true, 10.0, false))
                t(station_code, date_local, is_valid_day, pm25_mean, exceeds_24h_limit))
            TO '{folder / "fct_pm25_daily.parquet"}' (FORMAT parquet)
        """)
        con.execute(f"""
            COPY (SELECT 0 AS station_code, '' AS station_id, '' AS station_name,
                '' AS municipality) TO '{folder / "dim_stations.parquet"}' (FORMAT parquet)
        """)
    one_day = ANALYSIS.model_copy(update={"end": ANALYSIS.start})
    table, _ = station_ranking(folder, tmp_path / "rep", one_day)
    rows = list(csv.DictReader(table.open(encoding="utf-8")))
    assert [r["station_code"] for r in rows] == ["7", "5", "8", "9"]
    assert "mean_unrounded" not in rows[0]
