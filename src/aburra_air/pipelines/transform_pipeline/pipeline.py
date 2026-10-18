"""Transform pipeline: DuckDB raw tables -> dbt staging (03_primary) -> marts (05_model_input)."""

import os

from dbt.cli.main import dbtRunner

from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


class TransformError(RuntimeError):
    """dbt failed to build a model or a test failed."""


def dbt_env(config: Config) -> dict[str, str]:
    """Return the environment variables ``dbt/profiles.yml`` reads its paths from.

    Args:
        config: Project configuration.

    Returns:
        Variable name to absolute path.
    """
    return {
        "ABURRA_AIR_DUCKDB": str(config.paths.database),
        "ABURRA_AIR_INTERMEDIATE": str(config.paths.intermediate),
        "ABURRA_AIR_MODEL_INPUT": str(config.paths.model_input),
    }


def run(config: Config | None = None, command: str = "build") -> None:
    """Run a dbt command (``build`` by default) on the project in ``paths.dbt_project``.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
        command: dbt command, e.g. ``build`` or ``docs generate``.

    Raises:
        TransformError: If dbt reports a failure.
    """
    config = config or get_config()
    logger = get_logger(__name__, config.logging.level)
    logger.info("Reading from %s", config.paths.database)
    os.environ.update(dbt_env(config))
    for folder in (config.paths.intermediate, config.paths.model_input):
        folder.mkdir(parents=True, exist_ok=True)
    project = str(config.paths.dbt_project)
    args = [*command.split(), "--project-dir", project, "--profiles-dir", project]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise TransformError(f"dbt {command} failed: {result.exception or 'see the dbt log'}")
    logger.info("Writing to %s", config.paths.model_input)
