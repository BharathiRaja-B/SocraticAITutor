"""
database package — database helpers
Provides `get_db()` and `init_db()` used by the app.
This module reuses the existing schema creation logic from main.py.
"""
import sqlite3
import bcrypt
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
logger = get_logger("database")

DEFAULT_DB_PATH = "tutor.db"
_initializing = False


def get_db():
    # Read the path for each connection so tests and deployments can configure
    # DB_PATH before the first request, even after this module is imported.
    db_path = os.environ.get("DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Test clients may skip FastAPI lifespan events and may set DB_PATH after
    # importing the app. Initialize a newly selected database on first use.
    if not _initializing:
        has_users = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if has_users is None:
            conn.close()
            init_db()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

    return conn


def init_db():
    global _initializing
    _initializing = True
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'student',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            progress    INTEGER NOT NULL DEFAULT 0,
            hints_used  INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, topic)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            summary     TEXT,
            hints_used  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS explanations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            explanation TEXT NOT NULL,
            evaluation  TEXT,
            score       INTEGER,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            role        TEXT NOT NULL,
            message     TEXT NOT NULL,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roadmap_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roadmap_name TEXT NOT NULL,
            topic_order INTEGER NOT NULL,
            topic_name TEXT NOT NULL,
            UNIQUE(roadmap_name, topic_order)
        );

        CREATE TABLE IF NOT EXISTS user_roadmap_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            roadmap_name TEXT NOT NULL,
            topic_name TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            UNIQUE(user_id, roadmap_name, topic_name)
        );

        CREATE TABLE IF NOT EXISTS evaluation_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            failed_count INTEGER NOT NULL DEFAULT 0,
            total_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, topic)
        );

        CREATE TABLE IF NOT EXISTS user_weak_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            reason TEXT NOT NULL,
            mark_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, topic)
        );
    """)

    # Create a default admin account if none exists
    admin_exists = cur.execute(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()

    if not admin_exists:
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Admin", "admin@tutor.com", hashed, "admin", datetime.now(timezone.utc).isoformat()),
        )

    # Seed default roadmaps if none exist
    count = cur.execute("SELECT COUNT(*) FROM roadmap_topics").fetchone()[0]
    if count == 0:
        react = ["Components", "JSX", "Props", "State", "Hooks"]
        for i, t in enumerate(react, start=1):
            cur.execute(
                "INSERT INTO roadmap_topics (roadmap_name, topic_order, topic_name) VALUES (?, ?, ?)",
                ("React", i, t),
            )
        py = ["Variables", "Conditions", "Loops", "Functions", "OOP"]
        for i, t in enumerate(py, start=1):
            cur.execute(
                "INSERT INTO roadmap_topics (roadmap_name, topic_order, topic_name) VALUES (?, ?, ?)",
                ("Python", i, t),
            )

    conn.commit()
    conn.close()
    _initializing = False
    logger.info("Database initialized. Default admin: admin@tutor.com / admin123")


# Prepare the schema during import as well as application startup. This keeps
# direct ASGI clients and scripts safe when they do not trigger lifespan events.
init_db()


# Convenience DB helpers
from contextlib import contextmanager

@contextmanager
def db_connection():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def fetch_one(query: str, params: tuple = ()):
    with db_connection() as conn:
        cur = conn.execute(query, params)
        return cur.fetchone()


def fetch_all(query: str, params: tuple = ()):
    with db_connection() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()


def execute_query(query: str, params: tuple = ()):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid
