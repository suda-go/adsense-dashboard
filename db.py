"""SQLite cache layer for API responses and analysis results."""

import hashlib
import json
import sqlite3
import time

import config

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db():
    """Create cache tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS report_cache (
            query_key TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            fetched_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_cache (
            query_key TEXT PRIMARY KEY,
            analysis_json TEXT NOT NULL,
            generated_at REAL NOT NULL
        );
    """)
    conn.commit()


def make_cache_key(*parts) -> str:
    """Create a deterministic cache key from arbitrary parts."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# --- Report cache ---

def get_cached_report(key: str) -> dict | None:
    """Get cached report if still fresh (within TTL)."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT response_json, fetched_at FROM report_cache WHERE query_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    age = time.time() - row["fetched_at"]
    if age > config.REPORT_CACHE_TTL_SECONDS:
        return None
    return json.loads(row["response_json"])


def set_cached_report(key: str, data):
    """Store report data in cache."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO report_cache (query_key, response_json, fetched_at) VALUES (?, ?, ?)",
        (key, json.dumps(data, default=str), time.time()),
    )
    conn.commit()


# --- Analysis cache ---

def get_cached_analysis(key: str) -> dict | None:
    """Get cached analysis if still fresh."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT analysis_json, generated_at FROM analysis_cache WHERE query_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    age = time.time() - row["generated_at"]
    if age > config.ANALYSIS_CACHE_TTL_SECONDS:
        return None
    return json.loads(row["analysis_json"])


def set_cached_analysis(key: str, data):
    """Store analysis result in cache."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO analysis_cache (query_key, analysis_json, generated_at) VALUES (?, ?, ?)",
        (key, json.dumps(data, default=str), time.time()),
    )
    conn.commit()
