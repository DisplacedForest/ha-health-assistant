from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import StoreCorruptError, StoreError
from .schema import apply_migrations


class HealthDatabase:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def open(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA foreign_keys = ON")
                apply_migrations(conn)
            except StoreError:
                conn.close()
                raise
            except sqlite3.DatabaseError as err:
                conn.close()
                raise StoreCorruptError(
                    f"database at {self._path} is corrupt or unreadable: {err}"
                ) from err
            except BaseException:
                conn.close()
                raise
            self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    def backup(self, destination: Path) -> None:
        with self._lock:
            if self._conn is None:
                raise StoreError("database is not open")
            destination.parent.mkdir(parents=True, exist_ok=True)
            target = sqlite3.connect(destination)
            try:
                self._conn.backup(target)
            finally:
                target.close()

    def checkpoint(self) -> None:
        with self._lock:
            if self._conn is None:
                raise StoreError("database is not open")
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            if self._conn is None:
                raise StoreError("database is not open")
            with self._conn:
                return self._conn.execute(sql, tuple(params)).fetchall()

    def execute_batch(self, statements: Iterable[tuple[str, Iterable[Any]]]) -> None:
        with self._lock:
            if self._conn is None:
                raise StoreError("database is not open")
            with self._conn:
                for sql, params in statements:
                    self._conn.execute(sql, tuple(params))
