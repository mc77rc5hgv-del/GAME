"""SQLite storage for the interactive Avito Telegram bot.

One filter = one saved Avito search URL owned by a chat. Each filter tracks
its own check interval, active/paused state, failure streak and the set of
listing ids already seen (so only genuinely new ones get pushed).
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 15,
    active INTEGER NOT NULL DEFAULT 1,
    last_checked_at REAL NOT NULL DEFAULT 0,
    last_found_at REAL NOT NULL DEFAULT 0,
    total_found INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_alert_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    UNIQUE(chat_id, name)
);

CREATE TABLE IF NOT EXISTS seen_items (
    filter_id INTEGER NOT NULL REFERENCES filters(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    seen_at REAL NOT NULL,
    PRIMARY KEY (filter_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_seen_items_filter ON seen_items(filter_id);
"""

MAX_SEEN_PER_FILTER = 500


@dataclass
class Filter:
    id: int
    chat_id: int
    name: str
    url: str
    interval_minutes: int
    active: bool
    last_checked_at: float
    last_found_at: float
    total_found: int
    consecutive_failures: int
    last_alert_at: float
    created_at: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Filter":
        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            name=row["name"],
            url=row["url"],
            interval_minutes=row["interval_minutes"],
            active=bool(row["active"]),
            last_checked_at=row["last_checked_at"],
            last_found_at=row["last_found_at"],
            total_found=row["total_found"],
            consecutive_failures=row["consecutive_failures"],
            last_alert_at=row["last_alert_at"],
            created_at=row["created_at"],
        )


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- filters -----------------------------------------------------

    def add_filter(self, chat_id: int, name: str, url: str, interval_minutes: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO filters (chat_id, name, url, interval_minutes, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (chat_id, name, url, interval_minutes, time.time()),
            )
            return cur.lastrowid

    def filter_exists(self, chat_id: int, name: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM filters WHERE chat_id = ? AND name = ?", (chat_id, name)
            ).fetchone()
            return row is not None

    def count_filters(self, chat_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM filters WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            return row["n"]

    def get_filter(self, chat_id: int, name: str) -> Filter | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM filters WHERE chat_id = ? AND name = ?", (chat_id, name)
            ).fetchone()
            return Filter.from_row(row) if row else None

    def get_filter_by_id(self, filter_id: int) -> Filter | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM filters WHERE id = ?", (filter_id,)).fetchone()
            return Filter.from_row(row) if row else None

    def list_filters(self, chat_id: int) -> list[Filter]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM filters WHERE chat_id = ? ORDER BY created_at", (chat_id,)
            ).fetchall()
            return [Filter.from_row(r) for r in rows]

    def list_due_filters(self, now: float | None = None) -> list[Filter]:
        now = now if now is not None else time.time()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM filters WHERE active = 1 "
                "AND (? - last_checked_at) >= (interval_minutes * 60)",
                (now,),
            ).fetchall()
            return [Filter.from_row(r) for r in rows]

    def delete_filter(self, chat_id: int, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM filters WHERE chat_id = ? AND name = ?", (chat_id, name)
            )
            return cur.rowcount > 0

    def set_active(self, chat_id: int, name: str, active: bool) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE filters SET active = ? WHERE chat_id = ? AND name = ?",
                (1 if active else 0, chat_id, name),
            )
            return cur.rowcount > 0

    def set_interval(self, chat_id: int, name: str, minutes: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE filters SET interval_minutes = ? WHERE chat_id = ? AND name = ?",
                (minutes, chat_id, name),
            )
            return cur.rowcount > 0

    def mark_checked(
        self,
        filter_id: int,
        success: bool,
        new_found: int = 0,
    ) -> None:
        with self._connect() as conn:
            now = time.time()
            if success:
                conn.execute(
                    "UPDATE filters SET last_checked_at = ?, consecutive_failures = 0, "
                    "total_found = total_found + ?, "
                    "last_found_at = CASE WHEN ? > 0 THEN ? ELSE last_found_at END "
                    "WHERE id = ?",
                    (now, new_found, new_found, now, filter_id),
                )
            else:
                conn.execute(
                    "UPDATE filters SET last_checked_at = ?, "
                    "consecutive_failures = consecutive_failures + 1 WHERE id = ?",
                    (now, filter_id),
                )

    def mark_alerted(self, filter_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE filters SET last_alert_at = ? WHERE id = ?", (time.time(), filter_id)
            )

    # -- seen items ----------------------------------------------------

    def get_seen_ids(self, filter_id: int) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT item_id FROM seen_items WHERE filter_id = ?", (filter_id,)
            ).fetchall()
            return {r["item_id"] for r in rows}

    def add_seen_ids(self, filter_id: int, item_ids: list[str]) -> None:
        if not item_ids:
            return
        now = time.time()
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO seen_items (filter_id, item_id, seen_at) VALUES (?, ?, ?)",
                [(filter_id, item_id, now) for item_id in item_ids],
            )
            # keep only the most recent MAX_SEEN_PER_FILTER rows per filter
            conn.execute(
                """
                DELETE FROM seen_items
                WHERE filter_id = ? AND item_id NOT IN (
                    SELECT item_id FROM seen_items
                    WHERE filter_id = ?
                    ORDER BY seen_at DESC
                    LIMIT ?
                )
                """,
                (filter_id, filter_id, MAX_SEEN_PER_FILTER),
            )

    # -- global stats ----------------------------------------------------

    def global_stats(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS filters, "
                "SUM(active) AS active_filters, "
                "COUNT(DISTINCT chat_id) AS chats, "
                "SUM(total_found) AS total_found "
                "FROM filters"
            ).fetchone()
            return {
                "filters": row["filters"] or 0,
                "active_filters": row["active_filters"] or 0,
                "chats": row["chats"] or 0,
                "total_found": row["total_found"] or 0,
            }
