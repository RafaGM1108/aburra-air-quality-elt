import duckdb
import pytest

from aburra_air.pipelines.load_pipeline import pipeline as load_pipeline
from aburra_air.pipelines.transform_pipeline.pipeline import TransformError, run
from aburra_air.utils.config import Config


def test_build_creates_staging_views(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    with duckdb.connect(config.paths.database) as con:
        rows = con.sql("SELECT count(*) FROM staging.stg_siata__pm25_live").fetchone()
        assert rows == (144,)


def test_build_writes_marts_to_parquet(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    marts = sorted(p.name for p in config.paths.model_input.iterdir())
    assert marts == [
        "agg_pm25_hour_of_day.parquet",
        "agg_pm25_station_monthly.parquet",
        "dim_stations.parquet",
        "fct_pm25_daily.parquet",
        "fct_pm25_hourly.parquet",
    ]
    assert (config.paths.intermediate / "int_pm25_hourly.parquet").exists()


def test_daily_mean_needs_18_valid_hours_and_gets_an_ica(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    sql = """
        SELECT date_local::VARCHAR, valid_hours, round(pm25_mean, 1), exceeds_24h_limit, ica,
            ica_category
        FROM marts.fct_pm25_daily WHERE station_code = 12 ORDER BY date_local
    """
    with duckdb.connect(config.paths.database) as con:
        rows = con.sql(sql).fetchall()
    assert rows[0] == ("2026-10-07", 16, None, None, None, None)  # 16 < 18 valid hours
    assert rows[1] == ("2026-10-08", 24, 38.6, True, 101, "Dañina a la salud de grupos sensibles")
    assert rows[2] == ("2026-10-09", 21, 25.9, False, 76, "Aceptable")


def test_docs_generate_writes_the_catalog(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    run(config, "docs generate")
    assert (config.paths.dbt_project / "target" / "catalog.json").exists()


def test_station_text_is_trimmed(config: Config) -> None:
    load_pipeline.run(config)
    run(config)
    with duckdb.connect(config.paths.database) as con:
        sql = "SELECT municipality FROM staging.stg_siata__stations ORDER BY 1"
        assert con.sql(sql).fetchall() == [("Barbosa",), ("Medellín",)]  # raw is "Medellín "


def test_failed_build_raises(config: Config) -> None:
    with pytest.raises(TransformError, match="dbt build failed"):
        run(config)  # raw tables were never loaded
