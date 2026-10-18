"""Extract pipeline: SIATA / Open-Meteo APIs -> 01_raw (landing JSON)."""

from datetime import date

import httpx

from aburra_air.data import siata
from aburra_air.data.extract import extract_siata, today
from aburra_air.data.historical import backfill_siata
from aburra_air.data.open_meteo import extract_open_meteo
from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(
    config: Config | None = None,
    client: httpx.Client | None = None,
    run_date: date | None = None,
) -> None:
    """Run the extract pipeline.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
        client: HTTP client for SIATA and Open-Meteo. A new one is created if omitted.
        run_date: Date that names the landing folders. Today in Medellín if omitted.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    logger = get_logger(__name__, config.logging.level)
    logger.info("Writing to %s", config.paths.raw)
    run_date = run_date or today()
    with client or siata.make_client() as http:
        extract_siata(http, config.paths.raw, run_date)
        backfill_siata(http, config.paths.raw)  # one request ever, then a no-op
        extract_open_meteo(http, config.paths.raw, run_date)
