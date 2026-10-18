from pathlib import Path

from aburra_air.pipelines.load_pipeline import pipeline as load_pipeline
from aburra_air.pipelines.publish_pipeline.pipeline import run
from aburra_air.pipelines.transform_pipeline.pipeline import run as transform
from aburra_air.utils.config import Config


def test_run_stages_the_real_marts(config: Config, tmp_path: Path) -> None:
    paths = config.paths.model_copy(update={"publish": tmp_path / "publish"})
    config = config.model_copy(update={"paths": paths})
    load_pipeline.run(config)
    transform(config)
    staged = run(config)
    assert sorted(p.name for p in staged) == [
        "agg_pm25_station_monthly.parquet",
        "dim_stations.parquet",
        "fct_pm25_daily.parquet",
    ]
