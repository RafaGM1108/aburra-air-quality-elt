from datetime import date
from pathlib import Path

from aburra_air.pipelines.extract_pipeline.pipeline import run
from aburra_air.utils.config import get_config
from tests.conftest import RecordedSiata


def test_run_lands_into_configured_raw_folder(tmp_path: Path, siata_api: RecordedSiata) -> None:
    config = get_config()
    config = config.model_copy(update={"paths": config.paths.model_copy(update={"raw": tmp_path})})

    run(config, siata_api.client(), date(2026, 10, 10))

    landed = sorted(p.name for p in (tmp_path / "siata" / "pm25" / "2026-10-10").iterdir())
    assert landed == ["12.json", "81.json", "stations.json"]
