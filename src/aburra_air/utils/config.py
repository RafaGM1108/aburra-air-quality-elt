"""Typed loader for ``conf/base.yaml``."""

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

CONF_ENV_VAR = "ABURRA_AIR_CONF"
CONF_RELATIVE_PATH = Path("conf/base.yaml")


class ProjectConfig(BaseModel):
    """General project metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    random_seed: int = 42


class PathsConfig(BaseModel):
    """Locations of the data layers, relative to the project root."""

    model_config = ConfigDict(extra="forbid")

    raw: Path
    intermediate: Path
    primary: Path
    model_input: Path
    reporting: Path
    database: Path
    dbt_project: Path
    publish: Path


class LoggingConfig(BaseModel):
    """Logging settings."""

    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"


class QualityConfig(BaseModel):
    """Thresholds for the post-run data-quality checks."""

    model_config = ConfigDict(extra="forbid")

    max_lag_hours: int
    min_rows_latest_run: int
    min_stations_last_24h: int


class AnalysisConfig(BaseModel):
    """Window and coverage threshold for the analyses."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    min_coverage: float


class Config(BaseModel):
    """Root configuration object."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    paths: PathsConfig
    logging: LoggingConfig = LoggingConfig()
    quality: QualityConfig
    analysis: AnalysisConfig
    params: dict[str, Any] = {}


def find_config_file(start: Path | None = None) -> Path:
    """Locate the config file.

    Uses ``$ABURRA_AIR_CONF`` if set; otherwise walks up from ``start`` (default: the
    current directory) until it finds ``conf/base.yaml``. This works from the project
    root and from any subdirectory.

    Args:
        start: Directory to start searching from.

    Returns:
        Path to the config file.

    Raises:
        FileNotFoundError: If no config file can be found.
    """
    if env_path := os.environ.get(CONF_ENV_VAR):
        path = Path(env_path)
        if not path.is_file():
            raise FileNotFoundError(f"{CONF_ENV_VAR} points to a missing file: {path}")
        return path
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / CONF_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find {CONF_RELATIVE_PATH} above {here}")


def load_config(path: Path | None = None) -> Config:
    """Load and validate the configuration, resolving data paths against the project root.

    Args:
        path: Explicit config file. If omitted, :func:`find_config_file` is used.

    Returns:
        The validated configuration with absolute paths.
    """
    path = (path or find_config_file()).resolve()
    root = path.parent.parent
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = Config.model_validate(raw)
    resolved = {name: root / value for name, value in config.paths.model_dump().items()}
    return config.model_copy(update={"paths": PathsConfig(**resolved)})


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the configuration, loaded once per process."""
    return load_config()
