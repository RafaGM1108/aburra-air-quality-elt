from pathlib import Path

import pandas as pd

from aburra_air.analysis.weather import weather_relationship
from tests.conftest import ANALYSIS


def test_weather_relationship_writes_paired_days_and_correlations(
    marts: Path, tmp_path: Path
) -> None:
    written = weather_relationship(marts, tmp_path, ANALYSIS)

    assert [path.name for path in written] == ["pm25_weather_daily.csv", "pm25_weather_summary.csv"]
    daily = pd.read_csv(tmp_path / "pm25_weather_daily.csv")
    summary = pd.read_csv(tmp_path / "pm25_weather_summary.csv")
    assert len(daily) == 10
    assert list(summary.columns) == [
        "paired_days",
        "pm25_boundary_layer_height_correlation",
        "pm25_precipitation_correlation",
    ]
    assert summary.loc[0, "paired_days"] == 10
