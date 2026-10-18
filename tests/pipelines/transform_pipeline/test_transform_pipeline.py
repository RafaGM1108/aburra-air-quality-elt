import shutil
from pathlib import Path

import duckdb
import pytest

from aburra_air.pipelines.load_pipeline import pipeline as load_pipeline
from aburra_air.pipelines.transform_pipeline.pipeline import TransformError, run
from aburra_air.utils.config import Config, get_config
from tests.conftest import SIATA_FIXTURES


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Config with every data path under ``tmp_path`` and the fixtures landed in raw."""
    config = get_config()
    day = tmp_path / "raw" / "siata" / "pm25" / "2026-10-10"
    day.mkdir(parents=True)
    shutil.copy(SIATA_FIXTURES / "pm25_stations.json", day / "stations.json")
    for code in (12, 81):
        shutil.copy(SIATA_FIXTURES / f"pm25_72h_{code}.json", day / f"{code}.json")
    paths = config.paths.model_copy(
        update={
            "raw": tmp_path / "raw",
            "intermediate": tmp_path / "intermediate",
            "model_input": tmp_path / "model_input",
            "database": tmp_path / "primary" / "test.duckdb",
        }
    )
    return config.model_copy(update={"paths": paths})


def test_build_creates_staging_views(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    with duckdb.connect(config.paths.database) as con:
        rows = con.sql("SELECT count(*) FROM staging.stg_siata__pm25_live").fetchone()
        assert rows == (144,)


def test_failed_build_raises(config: Config) -> None:
    with pytest.raises(TransformError, match="dbt build failed"):
        run(config)  # raw tables were never loaded
