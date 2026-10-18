import csv
from pathlib import Path

from aburra_air.analysis.patterns import patterns
from tests.conftest import ANALYSIS


def read(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_writes_tables_and_figures(marts: Path, tmp_path: Path) -> None:
    written = patterns(marts, tmp_path, ANALYSIS)
    assert sorted(p.name for p in written) == [
        "diurnal_profile.csv",
        "diurnal_profile.png",
        "monthly_profile.csv",
        "monthly_profile.png",
        "weekday_profile.csv",
        "weekday_profile.png",
    ]


def test_diurnal_profile_means_and_full_coverage(marts: Path, tmp_path: Path) -> None:
    patterns(marts, tmp_path, ANALYSIS)
    rows = {(r["day_type"], r["hour_of_day"]): r for r in read(tmp_path / "diurnal_profile.csv")}
    assert rows["weekday", "7"]["pm25_mean"] == "40.0"
    assert rows["weekday", "8"]["pm25_mean"] == "30.0"
    assert rows["weekend", "7"]["pm25_mean"] == "20.0"
    # 1 station x 8 weekdays (or 2 weekend days) in the window, all valid.
    assert rows["weekday", "7"]["possible_hours"] == "8"
    assert rows["weekend", "7"]["coverage"] == "1.0"


def test_weekday_and_monthly_profiles_pool_stations(marts: Path, tmp_path: Path) -> None:
    patterns(marts, tmp_path, ANALYSIS)
    monthly = read(tmp_path / "monthly_profile.csv")
    assert len(monthly) == 1
    assert monthly[0]["month"] == "2024-01"
    assert monthly[0]["valid_days"] == "25"  # 10 + 10 + 5
    assert monthly[0]["station_days"] == "30"
    assert monthly[0]["exceedance_days"] == "10"  # 4 + 1 + 5
    weekdays = read(tmp_path / "weekday_profile.csv")
    assert weekdays[0]["weekday"] == "Monday"  # 2024-01-01 was a Monday
