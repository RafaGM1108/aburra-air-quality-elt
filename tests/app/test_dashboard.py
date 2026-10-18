from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from aburra_air.utils.config import CONF_ENV_VAR, find_config_file, get_config

APP = Path(__file__).parents[2] / "src" / "aburra_air" / "app" / "main.py"


@pytest.fixture
def app(marts: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AppTest]:
    """The dashboard configured to read the fixture marts (no network: all marts exist)."""
    monkeypatch.delenv(CONF_ENV_VAR, raising=False)
    conf = yaml.safe_load(find_config_file().read_text(encoding="utf-8"))
    conf["paths"]["model_input"] = str(marts)
    path = tmp_path / "conf" / "base.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(conf), encoding="utf-8")
    monkeypatch.setenv(CONF_ENV_VAR, str(path))
    get_config.cache_clear()
    yield AppTest.from_file(str(APP), default_timeout=60)
    get_config.cache_clear()


def test_dashboard_loads_without_exceptions(app: AppTest) -> None:
    app.run()
    assert not app.exception
    assert app.title[0].value == "PM2.5 in the Aburrá Valley"
    assert app.selectbox[0].options == ["AAA · Alpha", "BBB · Beta", "CCC · Gamma"]


def test_every_station_and_period_renders(app: AppTest) -> None:
    app.run()
    for station in app.selectbox[0].options:
        for period in app.radio[0].options:
            app.selectbox[0].set_value(station)
            app.radio[0].set_value(period)
            app.run()
            assert not app.exception, (station, period)


def test_empty_period_shows_a_message(app: AppTest) -> None:
    app.run()
    app.radio[0].set_value("Live (since 2026-10)").run()
    assert not app.exception
    assert any("No valid day in this period" in info.value for info in app.info)
