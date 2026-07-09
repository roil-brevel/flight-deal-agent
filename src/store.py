"""Append-only price store (SQLite).

Every observation is a row. We never overwrite — the growing table IS the
price history that powers deal detection and the dashboard sparklines.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at   TEXT    NOT NULL,
    goal_id       TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    basis         TEXT    NOT NULL,
    origin        TEXT    NOT NULL,
    destination   TEXT    NOT NULL,
    depart_date   TEXT,
    return_date   TEXT,
    price         REAL    NOT NULL,
    currency      TEXT    NOT NULL,
    airline       TEXT,
    transfers     INTEGER,
    deep_link     TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_route
    ON observations (goal_id, origin, destination, source);
CREATE INDEX IF NOT EXISTS idx_obs_time
    ON observations (observed_at);
"""


@contextmanager
def connect(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_observations(conn, rows: Iterable[dict]) -> int:
    cols = ("observed_at", "goal_id", "source", "basis", "origin",
            "destination", "depart_date", "return_date", "price",
            "currency", "airline", "transfers", "deep_link")
    payload = [tuple(r.get(c) for c in cols) for r in rows]
    if not payload:
        return 0
    conn.executemany(
        f"INSERT INTO observations ({','.join(cols)}) "
        f"VALUES ({','.join('?' for _ in cols)})",
        payload,
    )
    return len(payload)


def history_for_route(conn, goal_id: str, origin: str, destination: str,
                      source: str, days: int = 90) -> list[dict]:
    """All prices for a route+source within the last `days`, oldest first."""
    cur = conn.execute(
        """
        SELECT observed_at, price, depart_date, return_date, airline,
               transfers, deep_link, basis, currency
        FROM observations
        WHERE goal_id=? AND origin=? AND destination=? AND source=?
          AND observed_at >= datetime('now', ?)
        ORDER BY observed_at ASC
        """,
        (goal_id, origin, destination, source, f"-{days} days"),
    )
    return [dict(r) for r in cur.fetchall()]


def latest_per_route(conn, goal_id: str | None = None) -> list[dict]:
    """The most recent observation for each route+source (for the dashboard)."""
    q = """
        SELECT o.* FROM observations o
        JOIN (
            SELECT goal_id, origin, destination, source, MAX(observed_at) AS mx
            FROM observations
            {where}
            GROUP BY goal_id, origin, destination, source
        ) latest
        ON o.goal_id=latest.goal_id AND o.origin=latest.origin
           AND o.destination=latest.destination AND o.source=latest.source
           AND o.observed_at=latest.mx
        ORDER BY o.price ASC
    """
    where = "WHERE goal_id=?" if goal_id else ""
    params = (goal_id,) if goal_id else ()
    cur = conn.execute(q.format(where=where), params)
    return [dict(r) for r in cur.fetchall()]
