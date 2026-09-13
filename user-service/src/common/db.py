from collections.abc import Iterator

import psycopg
from psycopg import Connection

from common.config_manager import settings


def get_db_connection() -> Iterator[Connection]:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not configured.")

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
    ) as connection:
        yield connection
