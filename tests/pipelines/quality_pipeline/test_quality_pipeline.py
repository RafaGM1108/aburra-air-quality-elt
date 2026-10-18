from pathlib import Path

import duckdb
import pytest

from aburra_air.data.quality import QualityError
from aburra_air.pipelines.quality_pipeline.pipeline import run
from aburra_air.utils.config import get_config
from tests.data.test_quality import NOW, build_db


def test_run_checks_the_configured_database(tmp_path: Path) -> None:
    database = tmp_path / "test.duckdb"
    with duckdb.connect(database) as con:
        build_db(tmp_path / "raw", con)
    config = get_config()
    quality = config.quality.model_copy(update={"min_rows_latest_run": 100})
    config = config.model_copy(
        update={"paths": config.paths.model_copy(update={"database": database})}
    )

    run(
        config.model_copy(
            update={"quality": quality.model_copy(update={"min_stations_last_24h": 2})}
        ),
        NOW,
    )
    with pytest.raises(QualityError, match="row count"):
        run(config, NOW)  # default thresholds expect a full 23-station run
