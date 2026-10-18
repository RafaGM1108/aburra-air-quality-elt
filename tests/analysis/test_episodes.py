import csv
from pathlib import Path

import duckdb
import pytest

from aburra_air.analysis.episodes import Episode, detect_episodes, episodes, level_index
from tests.conftest import ANALYSIS


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, -1), (37.9, -1), (38.0, 0), (55.9, 0), (56.0, 1), (150.9, 1), (151.0, 2)],
)
def test_level_index_truncates_like_the_ica(value: float | None, expected: int) -> None:
    assert level_index(value) == expected


def test_no_episode_below_prevencion() -> None:
    assert detect_episodes([37.0] * 200) == []


def test_episode_starts_on_first_hour_in_range_and_ends_on_first_hour_below() -> None:
    series = [20.0] * 10 + [45.0] * 100 + [20.0] * 100
    assert detect_episodes(series) == [Episode(start=10, end=110, level="prevencion", peak=45.0)]


def test_short_spike_is_not_an_episode() -> None:
    # 12 h in range then back below: only 11 of the next 48 h stay in range (< 75%).
    assert detect_episodes([20.0] * 10 + [45.0] * 12 + [20.0] * 100) == []


def test_brief_dip_does_not_end_the_episode() -> None:
    series = [45.0] * 60 + [30.0] * 5 + [45.0] * 60 + [20.0] * 60
    assert detect_episodes(series) == [Episode(start=0, end=125, level="prevencion", peak=45.0)]


def test_escalates_to_the_highest_confirmed_level() -> None:
    series = [45.0] * 20 + [80.0] * 60 + [45.0] * 20 + [20.0] * 60
    (episode,) = detect_episodes(series)
    assert (episode.level, episode.peak, episode.end) == ("alerta", 80.0, 100)


def test_missing_hours_count_against_declaring() -> None:
    # In range only every other hour: 50% of the next 48 h, never declared.
    assert detect_episodes([45.0, None] * 100) == []


def test_episode_without_48_future_hours_stays_open() -> None:
    (episode,) = detect_episodes([20.0] * 5 + [45.0] * 60)
    assert episode.start == 5
    assert episode.end is None


def test_writes_episodes_from_the_hourly_mart(tmp_path: Path) -> None:
    folder = tmp_path / "marts"
    folder.mkdir()
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'America/Bogota'")
        # Station 9: 24 h at 20, 72 h at 60, 72 h at 10 µg/m³ from 2024-01-02 00:00 local.
        con.execute(f"""
            COPY (
                SELECT 9 AS station_code, ts AS timestamp_hour,
                    timezone('America/Bogota', ts)::DATE AS date_local,
                    CASE WHEN i < 24 THEN 20.0 WHEN i < 96 THEN 60.0 ELSE 10.0 END AS pm25
                FROM (SELECT i, TIMESTAMPTZ '2024-01-02 00:00:00-05' + i * INTERVAL 1 HOUR AS ts
                      FROM range(168) t(i))
            ) TO '{folder / "fct_pm25_hourly.parquet"}' (FORMAT parquet)
        """)
    (path,) = episodes(folder, tmp_path / "rep", ANALYSIS)
    (row,) = list(csv.DictReader(path.open(encoding="utf-8")))
    assert row["station_code"] == "9"
    assert row["level"] == "alerta"
    assert row["start"].endswith("-05:00")
    assert int(row["duration_hours"]) > 48


def test_skips_without_the_hourly_mart(tmp_path: Path) -> None:
    assert episodes(tmp_path, tmp_path / "rep", ANALYSIS) == []
