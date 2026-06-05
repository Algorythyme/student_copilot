from __future__ import annotations

import json
import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Generator, Optional
from urllib.parse import parse_qs, urlparse, unquote

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

SCHEMA = "student_copilot"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required for student_copilot Postgres backend")
    return url


def parse_database_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/railway").lstrip("/") or "railway",
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "sslmode": (query.get("sslmode") or ["prefer"])[0],
    }


@lru_cache()
def _pool() -> ThreadedConnectionPool:
    kwargs = parse_database_url(_database_url())
    return ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        options=f"-c search_path={SCHEMA},public",
        **kwargs,
    )


@contextmanager
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    pool = _pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def row_to_dict(row: Optional[psycopg2.extras.RealDictRow]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    out = dict(row)
    for key, val in list(out.items()):
        if hasattr(val, "isoformat"):
            out[key] = val.isoformat()
    return out


def rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows if r is not None]  # type: ignore[arg-type]


def json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)
