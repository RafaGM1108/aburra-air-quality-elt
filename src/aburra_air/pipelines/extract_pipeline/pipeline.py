"""Extract pipeline: SIATA / Open-Meteo APIs -> 01_raw (landing JSON)."""

from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None) -> None:
    """Run the extract pipeline.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
    """
    config = config or get_config()
    logger = get_logger(__name__, config.logging.level)
    logger.info("Reading from the source APIs")
    # TODO(phase 1): implement the extract step.
    logger.info("Writing to %s", config.paths.raw)
