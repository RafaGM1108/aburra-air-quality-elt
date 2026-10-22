import shutil
from pathlib import Path

import duckdb

from aburra_air.data.open_meteo import DAILY_DIR
from aburra_air.pipelines.load_pipeline.pipeline import run
from aburra_air.utils.config import get_config
from tests.conftest import OPEN_METEO_FIXTURE, SIATA_FIXTURES


def test_run_loads_into_configured_database(tmp_path: Path) -> None:
    day = tmp_path / "raw" / "siata" / "pm25" / "2026-10-10"
    day.mkdir(parents=True)
    shutil.copy(SIATA_FIXTURES / "pm25_72h_12.json", day / "12.json")
    weather = tmp_path / "raw" / DAILY_DIR
    weather.mkdir(parents=True)
    shutil.copy(OPEN_METEO_FIXTURE, weather / "2024-01-01.json")
    database = tmp_path / "primary" / "test.duckdb"
    config = get_config()
    paths = config.paths.model_copy(update={"raw": tmp_path / "raw", "database": database})
    config = config.model_copy(update={"paths": paths})

    run(config)

    with duckdb.connect(database) as con:
        assert con.sql("SELECT count(*) FROM raw.siata_pm25_hourly").fetchone() == (72,)
        assert con.sql("SELECT count(*) FROM raw.open_meteo_hourly").fetchone() == (3,)
