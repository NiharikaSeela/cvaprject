"""
SQLite data layer.

Tables
------
locations            Monitoring locations (reservoirs, canals, ...)
detection_reports    ONE row per (location, class). Repeated detections update
                     this row instead of inserting new rows.
detection_summaries  One short entry per image analysed or per drone-camera
                     reporting window. Used for duplicate prevention.
alerts               Alert history. At most one Active alert per location.
pub_submissions      Mock PUB submissions (Pending/Submitted/Failed), kept for
                     duplicate prevention and the latest status per location.
"""
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import config

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    area        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detection_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id         INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    class_name          TEXT NOT NULL,
    detection_count     INTEGER NOT NULL DEFAULT 0,
    highest_confidence  REAL NOT NULL DEFAULT 0,
    first_detected      TEXT NOT NULL,
    last_detected       TEXT NOT NULL,
    UNIQUE (location_id, class_name)
);

CREATE TABLE IF NOT EXISTS detection_summaries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id    INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    source         TEXT NOT NULL,
    source_ref     TEXT,
    summary        TEXT NOT NULL,
    total_objects  INTEGER NOT NULL,
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- The same image cannot be recorded twice for the same location
CREATE UNIQUE INDEX IF NOT EXISTS idx_summary_unique_ref
    ON detection_summaries(location_id, source_ref)
    WHERE source_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_summary_created
    ON detection_summaries(created_at);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id  INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    classes      TEXT NOT NULL,
    issues       TEXT NOT NULL,
    severity     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Active',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    resolved_at  TEXT
);

-- Only one active alert per location
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_alert
    ON alerts(location_id)
    WHERE status = 'Active';

CREATE TABLE IF NOT EXISTS pub_submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id   INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    alert_id      INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
    payload       TEXT NOT NULL,
    payload_hash  TEXT NOT NULL,
    status        TEXT NOT NULL,
    reference_id  TEXT,
    message       TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pub_location
    ON pub_submissions(location_id, id);
"""


def now_str() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


@contextmanager
def get_connection():
    """Open a connection, commit on success, roll back on error, always close."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def _one(cursor) -> dict | None:
    row = cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Online copy (Streamlit Community Cloud only)
# ---------------------------------------------------------------------------
def sync_cloud_database() -> None:
    """Copy the database from GitHub to the online working copy whenever a new one is pushed."""
    if not config.IS_STREAMLIT_CLOUD or not config.REPO_DB_PATH.exists():
        return
    info = config.REPO_DB_PATH.stat()
    signature = f"{info.st_mtime_ns}-{info.st_size}"
    marker = config.DB_PATH.with_suffix(".source")
    if config.DB_PATH.exists() and marker.exists() and marker.read_text() == signature:
        return
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(str(config.DB_PATH) + suffix).unlink(missing_ok=True)
    shutil.copy2(config.REPO_DB_PATH, config.DB_PATH)
    marker.write_text(signature)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode = WAL")
        ts = now_str()
        conn.executemany(
            "INSERT OR IGNORE INTO locations (name, area, created_at) VALUES (?, ?, ?)",
            [(name, area, ts) for name, area in config.DEFAULT_LOCATIONS],
        )


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
def get_locations() -> list[dict]:
    with get_connection() as conn:
        return _rows(conn.execute("SELECT * FROM locations ORDER BY name"))


def get_location(conn, location_id: int) -> dict | None:
    return _one(conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)))


def add_location(name: str, area: str = "") -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "Please enter a location name."
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO locations (name, area, created_at) VALUES (?, ?, ?)",
                (name, (area or "").strip(), now_str()),
            )
        return True, f"Location '{name}' added."
    except sqlite3.IntegrityError:
        return False, f"A location named '{name}' already exists."


# ---------------------------------------------------------------------------
# Detection reports (grouped by location + class)
# ---------------------------------------------------------------------------
def upsert_detection_report(conn, location_id, class_name, count, confidence, ts) -> None:
    """Insert a new grouped record or update the existing one for this location/class."""
    conn.execute(
        """
        INSERT INTO detection_reports
            (location_id, class_name, detection_count, highest_confidence,
             first_detected, last_detected)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(location_id, class_name) DO UPDATE SET
            detection_count    = detection_count + excluded.detection_count,
            highest_confidence = MAX(highest_confidence, excluded.highest_confidence),
            last_detected      = excluded.last_detected
        """,
        (location_id, class_name, int(count), float(confidence), ts, ts),
    )


def get_location_reports(conn, location_id: int) -> list[dict]:
    return _rows(conn.execute(
        "SELECT * FROM detection_reports WHERE location_id = ? ORDER BY detection_count DESC",
        (location_id,),
    ))


def get_all_reports() -> list[dict]:
    with get_connection() as conn:
        return _rows(conn.execute(
            """
            SELECT r.*, l.name AS location_name
            FROM detection_reports r JOIN locations l ON l.id = r.location_id
            ORDER BY l.name, r.detection_count DESC
            """
        ))


# ---------------------------------------------------------------------------
# Detection summaries (activity log)
# ---------------------------------------------------------------------------
def summary_exists(conn, location_id: int, source_ref: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM detection_summaries WHERE location_id = ? AND source_ref = ?",
        (location_id, source_ref),
    ).fetchone()
    return row is not None


def insert_detection_summary(conn, location_id, source, source_ref, summary,
                             total_objects, status, ts) -> None:
    conn.execute(
        """
        INSERT INTO detection_summaries
            (location_id, source, source_ref, summary, total_objects, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (location_id, source, source_ref, summary, int(total_objects), status, ts),
    )


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
def get_active_alert(conn, location_id: int) -> dict | None:
    return _one(conn.execute(
        "SELECT * FROM alerts WHERE location_id = ? AND status = 'Active'",
        (location_id,),
    ))


def get_alert(conn, alert_id: int) -> dict | None:
    return _one(conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)))


def create_alert(conn, location_id, classes, issues, severity, ts) -> int:
    cur = conn.execute(
        """
        INSERT INTO alerts (location_id, classes, issues, severity, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'Active', ?, ?)
        """,
        (location_id, classes, issues, severity, ts, ts),
    )
    return cur.lastrowid


def update_alert(conn, alert_id, classes, issues, severity, ts) -> None:
    conn.execute(
        "UPDATE alerts SET classes = ?, issues = ?, severity = ?, updated_at = ? WHERE id = ?",
        (classes, issues, severity, ts, alert_id),
    )


def resolve_alert(alert_id: int) -> None:
    ts = now_str()
    with get_connection() as conn:
        conn.execute(
            "UPDATE alerts SET status = 'Resolved', resolved_at = ?, updated_at = ? "
            "WHERE id = ? AND status = 'Active'",
            (ts, ts, alert_id),
        )


def get_active_alerts() -> list[dict]:
    with get_connection() as conn:
        return _rows(conn.execute(
            """
            SELECT a.*, l.name AS location_name
            FROM alerts a JOIN locations l ON l.id = a.location_id
            WHERE a.status = 'Active' ORDER BY a.updated_at DESC
            """
        ))


def get_alert_history(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        return _rows(conn.execute(
            """
            SELECT a.*, l.name AS location_name
            FROM alerts a JOIN locations l ON l.id = a.location_id
            ORDER BY a.id DESC LIMIT ?
            """,
            (limit,),
        ))


# ---------------------------------------------------------------------------
# Mock PUB submissions
# ---------------------------------------------------------------------------
def create_pub_submission(conn, location_id, alert_id, payload, payload_hash, status, ts) -> int:
    cur = conn.execute(
        """
        INSERT INTO pub_submissions
            (location_id, alert_id, payload, payload_hash, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (location_id, alert_id, payload, payload_hash, status, ts, ts),
    )
    return cur.lastrowid


def update_pub_submission(submission_id, status, reference_id, message) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE pub_submissions SET status = ?, reference_id = ?, message = ?, updated_at = ? "
            "WHERE id = ?",
            (status, reference_id, message, now_str(), submission_id),
        )


def get_last_pub_submission(conn, location_id: int) -> dict | None:
    return _one(conn.execute(
        "SELECT * FROM pub_submissions WHERE location_id = ? ORDER BY id DESC LIMIT 1",
        (location_id,),
    ))


def get_latest_pub_by_location() -> dict[int, dict]:
    with get_connection() as conn:
        rows = _rows(conn.execute(
            """
            SELECT p.* FROM pub_submissions p
            JOIN (SELECT location_id, MAX(id) AS max_id
                  FROM pub_submissions GROUP BY location_id) latest
              ON latest.max_id = p.id
            """
        ))
    return {row["location_id"]: row for row in rows}


# ---------------------------------------------------------------------------
# Dashboard counts
# ---------------------------------------------------------------------------
def get_counts() -> dict:
    with get_connection() as conn:
        def scalar(sql):
            return conn.execute(sql).fetchone()[0]

        return {
            "locations": scalar("SELECT COUNT(*) FROM locations"),
            "active_alerts": scalar("SELECT COUNT(*) FROM alerts WHERE status = 'Active'"),
            "reports": scalar("SELECT COUNT(*) FROM detection_reports"),
            "pub_submitted": scalar("SELECT COUNT(*) FROM pub_submissions WHERE status = 'Submitted'"),
        }
