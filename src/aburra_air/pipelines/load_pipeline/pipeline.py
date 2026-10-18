"""Load pipeline: 01_raw -> DuckDB raw tables, deduplicated."""

import duckdb

from aburra_air.data.load import load_siata
from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None) -> None:
    """Run the load pipeline.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    logger = get_logger(__name__, config.logging.level)
    logger.info("Reading from %s", config.paths.raw)
    config.paths.database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(config.paths.database) as con:
        con.execute("SET TimeZone = 'America/Bogota'")
        load_siata(config.paths.raw, con)
    logger.info("Wrote %s", config.paths.database)
