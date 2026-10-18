import shutil
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pytest

from aburra_air.data import siata
from aburra_air.data.historical import HISTORICAL_URL
from aburra_air.utils.config import AnalysisConfig, Config, get_config

SIATA_FIXTURES = Path(__file__).parent / "fixtures" / "siata"
OPEN_METEO_FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo" / "hourly.json"


class RecordedSiata:
    """Serves responses recorded from the SIATA geoportal; records every request.

    ``overrides`` maps a station code to the response (or exception) to return instead;
    ``historical`` is the response for the frozen historical file (hand-made fixture
    following the documented shape in ``docs/data.md``). Open-Meteo requests get a
    hand-made response in Open-Meteo's documented shape.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.overrides: dict[int, httpx.Response | Exception] = {}
        self.historical = httpx.Response(
            200, content=(SIATA_FIXTURES / "historical_pm25.json").read_bytes()
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host.endswith("open-meteo.com"):
            return httpx.Response(200, content=OPEN_METEO_FIXTURE.read_bytes())
        if request.url.path.endswith(siata.STATIONS_PATH):
            return httpx.Response(200, content=(SIATA_FIXTURES / "pm25_stations.json").read_bytes())
        if str(request.url) == HISTORICAL_URL:
            return self.historical
        code = int(request.url.path.rsplit("/", 1)[-1])
        override = self.overrides.get(code)
        if isinstance(override, Exception):
            raise override
        if override is not None:
            return override
        return httpx.Response(200, content=(SIATA_FIXTURES / f"pm25_72h_{code}.json").read_bytes())

    def client(self) -> httpx.Client:
        return siata.make_client(httpx.MockTransport(self))


@pytest.fixture
def siata_api() -> RecordedSiata:
    return RecordedSiata()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(siata.get.retry, "sleep", lambda _: None)


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


ANALYSIS = AnalysisConfig(start=date(2024, 1, 1), end=date(2024, 1, 10), min_coverage=0.75)


@pytest.fixture
def marts(tmp_path: Path) -> Path:
    """Daily and station marts for 3 stations over 2024-01-01..10.

    Station 1: 10 valid days, 4 above 37. Station 2: 10 valid days, 1 above 37.
    Station 3: 5 valid days (50% coverage), all above 37. 2024-01-01..10 has 8 weekdays and
    2 weekend days.
    """
    folder = tmp_path / "model_input"
    folder.mkdir()
    with duckdb.connect() as con:
        con.execute(f"""
            COPY (
                SELECT station_code, DATE '2024-01-01' + i::INTEGER AS date_local,
                    valid AS is_valid_day,
                    CASE WHEN valid THEN pm25 END AS pm25_mean,
                    CASE WHEN valid THEN pm25 > 37 END AS exceeds_24h_limit,
                    CASE WHEN valid AND pm25 > 37 THEN 'Dañina a la salud de grupos sensibles'
                        WHEN valid THEN 'Aceptable' END AS ica_category,
                    CASE WHEN valid THEN 80 END AS ica
                FROM (
                    SELECT 1 AS station_code, i, true AS valid,
                        CASE WHEN i < 4 THEN 50.0 ELSE 20.0 END AS pm25 FROM range(10) t(i)
                    UNION ALL
                    SELECT 2, i, true, CASE WHEN i = 0 THEN 40.0 ELSE 30.0 END FROM range(10) t(i)
                    UNION ALL
                    SELECT 3, i, i < 5, 60.0 FROM range(10) t(i)
                )
            ) TO '{folder / "fct_pm25_daily.parquet"}' (FORMAT parquet)
        """)
        con.execute(f"""
            COPY (SELECT * FROM (VALUES (1, 'AAA', 'Alpha', 'Medellín', 6.25, -75.57),
                (2, 'BBB', 'Beta', 'Bello', 6.33, -75.55),
                (3, 'CCC', 'Gamma', 'Itagüí', NULL, NULL))
                t(station_code, station_id, station_name, municipality, latitude, longitude))
            TO '{folder / "dim_stations.parquet"}' (FORMAT parquet)
        """)
        # Hour-of-day profile for January 2024: station 1 reports every hour, 30 µg/m³ on
        # weekdays and 20 µg/m³ on weekends, plus 10 µg/m³ extra at 07:00 on weekdays.
        con.execute(f"""
            COPY (
                SELECT 1 AS station_code, DATE '2024-01-01' AS month, h AS hour_of_day,
                    w AS is_weekend, n AS valid_hours, n * v AS pm25_sum, v AS pm25_mean
                FROM range(24) t(h), (VALUES (false, 8), (true, 2)) d(w, n),
                    LATERAL (SELECT CASE WHEN w THEN 20.0 WHEN h = 7 THEN 40.0 ELSE 30.0 END AS v)
            ) TO '{folder / "agg_pm25_hour_of_day.parquet"}' (FORMAT parquet)
        """)
        con.execute(f"""
            COPY (SELECT station_code, DATE '2024-01-01' AS month,
                    count(*) FILTER (WHERE is_valid_day) AS valid_days, avg(pm25_mean) AS pm25_mean,
                    count(*) FILTER (WHERE exceeds_24h_limit) AS exceedance_days
                FROM read_parquet('{folder / "fct_pm25_daily.parquet"}') GROUP BY ALL)
            TO '{folder / "agg_pm25_station_monthly.parquet"}' (FORMAT parquet)
        """)
    return folder
