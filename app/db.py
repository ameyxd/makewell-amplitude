"""Database access.

SQLite keeps everything in one file on disk. Each function here opens a
connection, does one job and closes it again.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("DATABASE_PATH", "makewell.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS workshops (
    id               INTEGER PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    category         TEXT NOT NULL,
    blurb            TEXT NOT NULL,
    description      TEXT NOT NULL,
    price_pence      INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL,
    tone             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workshop_sessions (
    id          INTEGER PRIMARY KEY,
    workshop_id INTEGER NOT NULL REFERENCES workshops (id),
    starts_at   TEXT NOT NULL,
    capacity    INTEGER NOT NULL,
    seats_taken INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def connect():
    """Open the database, save changes if all went well, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us write row["name"]
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the tables if they do not exist yet."""
    with connect() as conn:
        conn.executescript(SCHEMA)


def now_text():
    """The current time in the same text format we store dates in."""
    return datetime.now().isoformat(timespec="minutes")


def list_workshops():
    """Every workshop, with its next upcoming date and total seats left."""
    with connect() as conn:
        return conn.execute(
            """
            SELECT w.*,
                   MIN(s.starts_at) AS next_starts_at,
                   COALESCE(SUM(s.capacity - s.seats_taken), 0) AS seats_left
            FROM workshops w
            LEFT JOIN workshop_sessions s
                   ON s.workshop_id = w.id AND s.starts_at > ?
            GROUP BY w.id
            ORDER BY w.id
            """,
            (now_text(),),
        ).fetchall()


def get_workshop(slug):
    """One workshop by its web address name, or None."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM workshops WHERE slug = ?", (slug,)
        ).fetchone()


def list_sessions(workshop_id):
    """Upcoming dated sessions for one workshop, soonest first."""
    with connect() as conn:
        return conn.execute(
            """
            SELECT *, capacity - seats_taken AS seats_left
            FROM workshop_sessions
            WHERE workshop_id = ? AND starts_at > ?
            ORDER BY starts_at
            """,
            (workshop_id, now_text()),
        ).fetchall()
