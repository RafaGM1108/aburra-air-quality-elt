import hashlib
import json
from pathlib import Path

import duckdb
import httpx
import pytest

from aburra_air.data.publish import (
    PUBLISHABLE,
    RELEASE_API,
    PublishError,
    fetch_reporting,
    stage_publication,
)


def write_parquet(path: Path, select: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as con:
        con.execute(f"COPY ({select}) TO '{path}' (FORMAT parquet)")


@pytest.fixture
def model_input(tmp_path: Path) -> Path:
    folder = tmp_path / "model_input"
    for name in PUBLISHABLE:
        write_parquet(folder / f"{name}.parquet", "SELECT 12 AS station_code, 20.5 AS pm25_mean")
    write_parquet(folder / "fct_pm25_hourly.parquet", "SELECT now() AS timestamp_hour")
    return folder


def test_stages_only_the_publishable_marts(model_input: Path, tmp_path: Path) -> None:
    out = tmp_path / "publish"
    (out / "stale.duckdb").parent.mkdir()
    (out / "stale.duckdb").write_text("left over")
    staged = stage_publication(model_input, out)
    assert sorted(p.name for p in staged) == sorted(f"{n}.parquet" for n in PUBLISHABLE)
    assert sorted(p.name for p in out.iterdir()) == sorted(p.name for p in staged)


def test_refuses_a_mart_with_hourly_columns(model_input: Path, tmp_path: Path) -> None:
    write_parquet(model_input / "fct_pm25_daily.parquet", "SELECT 1 AS hour_local")
    with pytest.raises(PublishError, match="hourly columns"):
        stage_publication(model_input, tmp_path / "publish")


def test_refuses_when_a_mart_is_missing(model_input: Path, tmp_path: Path) -> None:
    (model_input / "dim_stations.parquet").unlink()
    with pytest.raises(PublishError, match="missing"):
        stage_publication(model_input, tmp_path / "publish")


def test_fetch_reporting_downloads_outputs_and_records_provenance(tmp_path: Path) -> None:
    release = {
        "html_url": "https://github.com/x/y/releases/tag/data-latest",
        "published_at": "2026-10-18T19:00:00Z",
        "assets": [
            {
                "name": "station_ranking.csv",
                "updated_at": "2026-10-18T19:22:50Z",
                "browser_download_url": "https://dl/station_ranking.csv",
            },
            {"name": "fct_pm25_daily.parquet", "browser_download_url": "https://dl/daily.parquet"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL(RELEASE_API):
            return httpx.Response(200, json=release)
        assert request.url.path == "/station_ranking.csv"  # Parquet marts are not fetched
        return httpx.Response(200, content=b"rank\n1\n")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        written = fetch_reporting(client, tmp_path)

    assert [p.name for p in written] == ["station_ranking.csv", "provenance.json"]
    provenance = json.loads((tmp_path / "provenance.json").read_text())
    assert provenance["published_at"] == "2026-10-18T19:00:00Z"
    assert provenance["files"] == [
        {
            "name": "station_ranking.csv",
            "updated_at": "2026-10-18T19:22:50Z",
            "sha256": hashlib.sha256(b"rank\n1\n").hexdigest(),
        }
    ]
