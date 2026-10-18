"""Quality pipeline: data-quality checks on DuckDB after load and transform."""

from datetime import datetime

import duckdb

from aburra_air.data.extract import TIMEZONE
from aburra_air.data.quality import check_all
from aburra_air.utils.config import Config, get_config
from aburra_air.utils.log import get_logger


def run(config: Config | None = None, now: datetime | None = None) -> None:
    """Run every data-quality check; raise if any fails.

    Args:
        config: Project configuration. Loaded from ``conf/base.yaml`` if omitted.
        now: Current time. Now in Medellín if omitted.
    """
    config = config or get_config()
    get_logger("aburra_air", config.logging.level)  # module loggers propagate here
    with duckdb.connect(config.paths.database, read_only=True) as con:
        check_all(con, config.quality, now or datetime.now(TIMEZONE))
