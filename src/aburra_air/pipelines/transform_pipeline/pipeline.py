"""Transform pipeline: dbt staging (03_primary) -> marts (05_model_input)."""

from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None) -> None:
    """Run the transform pipeline.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
    """
    config = config or get_config()
    logger = get_logger(__name__, config.logging.level)
    logger.info("Reading from %s", config.paths.primary)
    # TODO(phase 3): implement the transform step.
    logger.info("Writing to %s", config.paths.model_input)
