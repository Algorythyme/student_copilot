# database.py — Postgres student_copilot schema (Supabase-compatible table API)
from typing import Optional

from config import logger

_store = None


def get_db_store():
    global _store
    if _store is None:
        from db.postgres_store import PostgresStore

        _store = PostgresStore()
        logger.info("[database] Postgres student_copilot store initialized.")
    return _store


def get_supabase():
    """Compatibility alias — returns Postgres store instead of Supabase client."""
    try:
        return get_db_store()
    except Exception as exc:
        logger.error("[database] Postgres store unavailable: %s", exc)
        return None
