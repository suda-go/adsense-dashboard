"""Cache layer - uses SQLite locally, falls back to in-memory dict on serverless."""

import hashlib
import json
import sqlite3
import time

import config

_conn: sqlite3.Connection | None = None
_use_memory = False
_memory_cache: dict[str, tuple[float, any]] = {}


def _get_conn() -> sqlite3.Connection | None:
    global _conn, _use_memory
    if _use_memory:
        return None
    if _conn is None:
        try:
            _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
        except Exception:
            _use_memory = True
            return None
    return _conn


def init_db():
    """Create cache tables if they don't exist."""
    conn = _get_conn()
    if conn is None:
        return  # using memory fallback
    try:
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
    except Exception:
        pass


def make_cache_key(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# --- Report cache ---

def get_cached_report(key: str) -> dict | None:
    conn = _get_conn()
    if conn is None:
        # Memory fallback
        entry = _memory_cache.get(f"r:{key}")
        if entry and (time.time() - entry[0]) < config.REPORT_CACHE_TTL_SECONDS:
            return entry[1]
        return None

    row = conn.execute(
        "SELECT response_json, fetched_at FROM report_cache WHERE query_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    if (time.time() - row["fetched_at"]) > config.REPORT_CACHE_TTL_SECONDS:
        return None
    return json.loads(row["response_json"])


def set_cached_report(key: str, data):
    conn = _get_conn()
    if conn is None:
        _memory_cache[f"r:{key}"] = (time.time(), data)
        return

    conn.execute(
        "INSERT OR REPLACE INTO report_cache (query_key, response_json, fetched_at) VALUES (?, ?, ?)",
        (key, json.dumps(data, default=str), time.time()),
    )
    conn.commit()


# --- Analysis cache ---

def get_cached_analysis(key: str) -> dict | None:
    conn = _get_conn()
    if conn is None:
        entry = _memory_cache.get(f"a:{key}")
        if entry and (time.time() - entry[0]) < config.ANALYSIS_CACHE_TTL_SECONDS:
            return entry[1]
        return None

    row = conn.execute(
        "SELECT analysis_json, generated_at FROM analysis_cache WHERE query_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    if (time.time() - row["generated_at"]) > config.ANALYSIS_CACHE_TTL_SECONDS:
        return None
    return json.loads(row["analysis_json"])


def set_cached_analysis(key: str, data):
    conn = _get_conn()
    if conn is None:
        _memory_cache[f"a:{key}"] = (time.time(), data)
        return

    conn.execute(
        "INSERT OR REPLACE INTO analysis_cache (query_key, analysis_json, generated_at) VALUES (?, ?, ?)",
        (key, json.dumps(data, default=str), time.time()),
    )
    conn.commit()
