import csv
from pathlib import Path

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
