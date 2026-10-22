from pathlib import Path

from aburra_air.pipelines.analysis_pipeline.pipeline import run
from aburra_air.utils.config import get_config
from tests.conftest import ANALYSIS


def test_run_writes_reporting_outputs(marts: Path, tmp_path: Path) -> None:
    config = get_config()
    paths = config.paths.model_copy(update={"model_input": marts, "reporting": tmp_path / "rep"})
    written = run(config.model_copy(update={"paths": paths, "analysis": ANALYSIS}))
    assert {p.name for p in written} >= {
        "station_ranking.csv",
        "station_ranking.png",
        "pm25_weather_daily.csv",
        "pm25_weather_summary.csv",
    }
