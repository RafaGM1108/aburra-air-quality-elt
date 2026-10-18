import csv
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import duckdb
import pytest

from aburra_air.analysis.forecast import forecast_baselines
from aburra_air.utils.config import AnalysisConfig

WINDOW = AnalysisConfig(start=date(2024, 1, 1), end=date(2024, 1, 31), min_coverage=0.75)


def write_daily(folder: Path, values: Sequence[float | None]) -> Path:
    """One station, one daily mean per day from 2024-01-01; None = invalid day."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = ", ".join(
        f"(1, DATE '2024-01-01' + {i}::INTEGER, {'false' if v is None else 'true'}, {v or 'NULL'})"
        for i, v in enumerate(values)
    )
    with duckdb.connect() as con:
        con.execute(f"""
            COPY (SELECT * FROM (VALUES {rows})
                t(station_code, date_local, is_valid_day, pm25_mean))
            TO '{folder / "fct_pm25_daily.parquet"}' (FORMAT parquet)
        """)
    return folder


def metrics(folder: Path, tmp_path: Path) -> dict[str, dict[str, str]]:
    (path,) = forecast_baselines(folder, tmp_path / "rep", WINDOW)
    return {row["method"]: row for row in csv.DictReader(path.open(encoding="utf-8"))}


def test_constant_series_is_forecast_perfectly(tmp_path: Path) -> None:
    result = metrics(write_daily(tmp_path / "m", [20.0] * 20), tmp_path)
    assert set(result) == {"persistence", "mean_7d", "seasonal_naive_7d"}
    assert {row["mae"] for row in result.values()} == {"0.0"}
    assert result["persistence"]["n"] == "13"  # days 8..20 have yesterday, last week, 7 days


def test_weekly_cycle_favours_seasonal_naive(tmp_path: Path) -> None:
    week = [10.0, 10.0, 10.0, 10.0, 10.0, 40.0, 40.0]  # weekend spikes
    result = metrics(write_daily(tmp_path / "m", week * 4), tmp_path)
    assert result["seasonal_naive_7d"]["mae"] == "0.0"
    assert float(result["persistence"]["mae"]) > 0
    assert float(result["seasonal_naive_7d"]["skill_vs_persistence"]) == pytest.approx(1.0)


def test_invalid_days_are_neither_targets_nor_inputs(tmp_path: Path) -> None:
    values: list[float | None] = [20.0] * 20
    values[10] = None
    result = metrics(write_daily(tmp_path / "m", values), tmp_path)
    # Day 10 is no target; days 11 (no yesterday) and 17 (no last week) drop out too.
    assert result["persistence"]["n"] == "10"
