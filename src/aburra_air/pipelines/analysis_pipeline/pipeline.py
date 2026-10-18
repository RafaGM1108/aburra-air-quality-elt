"""Analysis pipeline: marts (05_model_input) -> tables and figures (08_reporting)."""

from pathlib import Path

from aburra_air.analysis.ranking import station_ranking
from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None) -> list[Path]:
    """Run every analysis on the marts and write its outputs to ``paths.reporting``.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.

    Returns:
        The written files.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    paths = config.paths
    return station_ranking(paths.model_input, paths.reporting, config.analysis)
