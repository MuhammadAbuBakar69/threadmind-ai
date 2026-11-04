"""Database session factory.

The engine is created lazily. Importing the application must not require a reachable database or
even an installed driver — liveness checks, OpenAPI generation, and the test suite all import this
module, and none of them should fall over because Postgres is not running.
"""

from collections.abc import Iterator
from functools import lru_cache

from core.config import get_settings
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
