"""Publish pipeline: stage the aggregated marts for the data release."""

from pathlib import Path

from aburra_air.data.publish import stage_publication
from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None) -> list[Path]:
    """Stage the publishable marts in ``paths.publish``.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.

    Returns:
        The staged files.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    return stage_publication(config.paths.model_input, config.paths.publish)
