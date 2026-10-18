"""Publish pipeline: stage the aggregated marts for the data release."""

from pathlib import Path

import httpx

from aburra_air.data.publish import fetch_reporting, stage_publication
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


def fetch(config: Config | None = None, client: httpx.Client | None = None) -> list[Path]:
    """Download the latest published analysis outputs into ``paths.reporting``.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
        client: HTTP client. A new one following redirects is created if omitted.

    Returns:
        The written files.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    with client or httpx.Client(follow_redirects=True, timeout=60) as http:
        return fetch_reporting(http, config.paths.reporting)
