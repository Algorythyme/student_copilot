#!/usr/bin/env python3
"""Apply student_copilot DDL to DATABASE_URL from student_copilot/.env."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "student_copilot_schema.sql"


def parse_url(url: str) -> dict:
    from urllib.parse import parse_qs, urlparse, unquote

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


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"')
                    break
    if not url:
        print("Set DATABASE_URL in environment or student_copilot/.env", file=sys.stderr)
        return 1

    sql = SQL_FILE.read_text(encoding="utf-8")
    kwargs = parse_url(url)
    conn = psycopg2.connect(**kwargs)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
        print(f"Applied {SQL_FILE.name} to {kwargs['dbname']}@{kwargs['host']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
