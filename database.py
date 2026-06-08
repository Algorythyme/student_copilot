"""Postgres student_copilot schema access."""

from config import logger

_store = None


def get_db_store():
    global _store
    if _store is None:
        from db.postgres_store import PostgresStore

        _store = PostgresStore()
        logger.info("[database] Postgres student_copilot store initialized.")
    return _store
