"""SQLite-backed application tracker.

Read-before-write by design: `track_application` only ever inserts or
updates a row the caller can already identify (by id for updates), never
performs a bulk/implicit mutation. Schema is created lazily on first use
so importing this module has no side effects (important for tests, which
point JOBMATCH_DB_PATH at a throwaway file).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from .errors import ApplicationNotFoundError, InvalidQueryError

VALID_STATUSES = {"saved", "applied", "interviewing", "offer", "rejected", "withdrawn"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    job_url TEXT,
    status TEXT NOT NULL,
    match_score INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def _connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def track_application(
    db_path: str,
    job_title: str,
    company: str,
    status: str = "saved",
    job_url: str | None = None,
    match_score: int | None = None,
    notes: str | None = None,
    application_id: int | None = None,
) -> dict:
    """Insert a new tracked application, or update an existing one by id."""
    if status not in VALID_STATUSES:
        raise InvalidQueryError(
            f"`status` must be one of {sorted(VALID_STATUSES)}, got '{status}'."
        )
    if not job_title.strip() or not company.strip():
        raise InvalidQueryError("`job_title` and `company` must be non-empty.")

    with _connect(db_path) as conn:
        if application_id is not None:
            existing = conn.execute(
                "SELECT id FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
            if existing is None:
                raise ApplicationNotFoundError(
                    f"No tracked application with id {application_id}."
                )
            conn.execute(
                """UPDATE applications
                   SET job_title=?, company=?, job_url=?, status=?, match_score=?, notes=?, updated_at=?
                   WHERE id=?""",
                (job_title, company, job_url, status, match_score, notes, _now(), application_id),
            )
            row_id = application_id
        else:
            cursor = conn.execute(
                """INSERT INTO applications
                   (job_title, company, job_url, status, match_score, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_title, company, job_url, status, match_score, notes, _now(), _now()),
            )
            row_id = cursor.lastrowid

        row = conn.execute("SELECT * FROM applications WHERE id=?", (row_id,)).fetchone()
        return dict(row)


def list_applications(db_path: str, status: str | None = None) -> list[dict]:
    if status is not None and status not in VALID_STATUSES:
        raise InvalidQueryError(
            f"`status` must be one of {sorted(VALID_STATUSES)}, got '{status}'."
        )
    with _connect(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
