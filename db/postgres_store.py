"""PostgREST-style client for student_copilot tables (db_store API compatibility)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import psycopg2.extras

from db.connection import db_connection, json_dumps, row_to_dict, rows_to_dicts

ALLOWED_TABLES = frozenset({"users", "conversations", "parent_chunks"})

JSON_COLUMNS = frozenset({"profile_override", "summaries"})


@dataclass
class ExecuteResult:
    data: list[dict[str, Any]] = field(default_factory=list)


class PostgresTableQuery:
    def __init__(self, table: str):
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Table not allowed: {table}")
        self.table = table
        self._select = "*"
        self._filters: list[tuple[str, str, Any]] = []
        self._is_null: list[str] = []
        self._ilike: list[tuple[str, str]] = []
        self._order: Optional[tuple[str, bool]] = None
        self._limit: Optional[int] = None
        self._insert_row: Optional[dict[str, Any]] = None
        self._update_row: Optional[dict[str, Any]] = None
        self._upsert_row: Optional[dict[str, Any]] = None
        self._upsert_conflict: str = "id"
        self._delete = False

    def select(self, columns: str = "*") -> "PostgresTableQuery":
        self._select = columns
        return self

    def eq(self, column: str, value: Any) -> "PostgresTableQuery":
        self._filters.append(("eq", column, value))
        return self

    def is_(self, column: str, value: str) -> "PostgresTableQuery":
        if value == "null":
            self._is_null.append(column)
        return self

    def ilike(self, column: str, pattern: str) -> "PostgresTableQuery":
        self._ilike.append((column, pattern))
        return self

    def order(self, column: str, desc: bool = False) -> "PostgresTableQuery":
        self._order = (column, desc)
        return self

    def limit(self, count: int) -> "PostgresTableQuery":
        self._limit = count
        return self

    def insert(self, row: dict[str, Any]) -> "PostgresTableQuery":
        self._insert_row = row
        return self

    def update(self, row: dict[str, Any]) -> "PostgresTableQuery":
        self._update_row = row
        return self

    def upsert(self, row: dict[str, Any], on_conflict: str = "id") -> "PostgresTableQuery":
        self._upsert_row = row
        self._upsert_conflict = on_conflict
        return self

    def delete(self) -> "PostgresTableQuery":
        self._delete = True
        return self

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        for key in JSON_COLUMNS:
            if key in out and out[key] is not None and not isinstance(out[key], str):
                out[key] = json_dumps(out[key])
        return out

    def _where_sql(self, start_index: int = 1) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for op, column, value in self._filters:
            if op == "eq":
                clauses.append(f"{column} = %s")
                if column.endswith("_id") and value is not None:
                    params.append(str(value))
                else:
                    params.append(value)
        for column in self._is_null:
            clauses.append(f"{column} IS NULL")
        for column, pattern in self._ilike:
            clauses.append(f"{column} ILIKE %s")
            params.append(pattern)
        if not clauses:
            return "", params
        return " WHERE " + " AND ".join(clauses), params

    def execute(self) -> ExecuteResult:
        with db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            if self._upsert_row is not None:
                row = self._serialize_row(self._upsert_row)
                cols = list(row.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                col_sql = ", ".join(cols)
                conflict = self._upsert_conflict
                updates = ", ".join(
                    f"{c} = EXCLUDED.{c}" for c in cols if c != conflict
                )
                if not updates:
                    updates = f"{conflict} = EXCLUDED.{conflict}"
                sql = (
                    f"INSERT INTO {self.table} ({col_sql}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict}) DO UPDATE SET {updates} RETURNING *"
                )
                cur.execute(sql, [row[c] for c in cols])
                inserted = row_to_dict(cur.fetchone())
                return ExecuteResult(data=[inserted] if inserted else [])

            if self._insert_row is not None:
                row = self._serialize_row(self._insert_row)
                cols = list(row.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                col_sql = ", ".join(cols)
                sql = (
                    f"INSERT INTO {self.table} ({col_sql}) VALUES ({placeholders}) "
                    f"RETURNING *"
                )
                cur.execute(sql, [row[c] for c in cols])
                inserted = row_to_dict(cur.fetchone())
                return ExecuteResult(data=[inserted] if inserted else [])

            if self._update_row is not None:
                row = self._serialize_row(self._update_row)
                set_parts = [f"{k} = %s" for k in row]
                set_params = list(row.values())
                where_sql, where_params = self._where_sql(len(set_params) + 1)
                touch = (
                    ", updated_at = NOW()"
                    if self.table == "conversations"
                    else ""
                )
                sql = f"UPDATE {self.table} SET {', '.join(set_parts)}{touch}{where_sql} RETURNING *"
                cur.execute(sql, set_params + where_params)
                return ExecuteResult(data=rows_to_dicts(cur.fetchall()))

            if self._delete:
                where_sql, where_params = self._where_sql()
                sql = f"DELETE FROM {self.table}{where_sql} RETURNING id"
                cur.execute(sql, where_params)
                return ExecuteResult(data=rows_to_dicts(cur.fetchall()))

            where_sql, where_params = self._where_sql()
            sql = f"SELECT {self._select} FROM {self.table}{where_sql}"
            if self._order:
                col, desc = self._order
                direction = "DESC" if desc else "ASC"
                sql += f" ORDER BY {col} {direction}"
            if self._limit is not None:
                sql += f" LIMIT {int(self._limit)}"

            cur.execute(sql, where_params)
            return ExecuteResult(data=rows_to_dicts(cur.fetchall()))


class PostgresStore:
    def table(self, name: str) -> PostgresTableQuery:
        return PostgresTableQuery(name)
