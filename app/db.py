"""Database access.

SQLite keeps everything in one file on disk. Each function here opens a
connection, does one job and closes it again.
"""
import os
import sqlite3
import uuid
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

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id                  INTEGER PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users (id),
    workshop_session_id INTEGER NOT NULL REFERENCES workshop_sessions (id),
    seats               INTEGER NOT NULL,
    amount_pence        INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'confirmed',
    created_at          TEXT NOT NULL,
    cancelled_at        TEXT
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


def get_session(workshop_session_id):
    """One dated session, with its workshop's name and price. None if missing."""
    with connect() as conn:
        return conn.execute(
            """
            SELECT s.*,
                   s.capacity - s.seats_taken AS seats_left,
                   w.slug, w.name AS workshop_name, w.category,
                   w.price_pence, w.tone
            FROM workshop_sessions s
            JOIN workshops w ON w.id = s.workshop_id
            WHERE s.id = ?
            """,
            (workshop_session_id,),
        ).fetchone()


def create_booking(user_id, workshop_session_id, seats, amount_pence):
    """Take the seats and save the booking.

    Returns the new booking's id, or None if there were not enough seats.
    The UPDATE only changes a row when enough seats remain, so two people
    booking at the same moment cannot both get the last seat.
    """
    with connect() as conn:
        taken = conn.execute(
            """
            UPDATE workshop_sessions
            SET seats_taken = seats_taken + ?
            WHERE id = ? AND capacity - seats_taken >= ?
            """,
            (seats, workshop_session_id, seats),
        )
        if taken.rowcount == 0:
            return None

        booking = conn.execute(
            """
            INSERT INTO bookings
                (user_id, workshop_session_id, seats, amount_pence, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, workshop_session_id, seats, amount_pence, now_text()),
        )
        return booking.lastrowid


def get_booking(booking_id):
    """One booking, with its workshop name and date. None if missing."""
    with connect() as conn:
        return conn.execute(
            """
            SELECT b.*, s.starts_at, w.name AS workshop_name, w.slug, w.category
            FROM bookings b
            JOIN workshop_sessions s ON s.id = b.workshop_session_id
            JOIN workshops w ON w.id = s.workshop_id
            WHERE b.id = ?
            """,
            (booking_id,),
        ).fetchone()


def create_user(email, display_name, password_hash, salt):
    """Save a new user and return their id, e.g. 'usr_3f9a...'."""
    user_id = "usr_" + uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users
                (id, email, display_name, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, display_name, password_hash, salt, now_text()),
        )
    return user_id


def get_user(user_id):
    """One user by id, or None."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def get_user_by_email(email):
    """One user by email, or None."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
