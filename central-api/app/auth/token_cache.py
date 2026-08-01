"""SQLite-backed token cache shared across uvicorn workers, with audit logging."""
import json
import logging
import os
import sqlite3
import time
from typing import NamedTuple, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)
audit = logging.getLogger("ph.audit")


class CacheEntry(NamedTuple):
    token: str
    created_at: float
    groups_bitmask: int
    source: str


_db_path: Optional[str] = None


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _get_db_path() -> str:
    global _db_path
    if _db_path is None:
        settings = get_settings()
        _db_path = settings.token_cache_path.replace(".enc", ".db")
    return _db_path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def init_db() -> None:
    """Create the tokens table if it doesn't exist."""
    path = _get_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                email TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                groups_bitmask INTEGER NOT NULL,
                source TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()
    logger.info("token cache DB initialized at %s", path)


def _purge_expired(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tokens WHERE expires_at <= ?", (time.time(),))


# ── Public API ──────────────────────────────────────────────────────────────


def cache_token(email: str, token: str, groups_bitmask: int, source: str) -> None:
    now = time.time()
    ttl = get_settings().api_key_ttl_days * 86400
    expires_at = now + ttl
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tokens (email, token, created_at, expires_at, groups_bitmask, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, token, now, expires_at, groups_bitmask, source),
        )
        conn.commit()
    finally:
        conn.close()
    audit.info(json.dumps({
        "audit": "token_issued",
        "email": email,
        "timestamp": _iso(now),
        "groups_bitmask": groups_bitmask,
        "source": source,
    }))


def get_cached_token(email: str) -> Optional[CacheEntry]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT token, created_at, groups_bitmask, source FROM tokens "
            "WHERE email = ? AND expires_at > ?",
            (email, time.time()),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return CacheEntry(token=row[0], created_at=row[1], groups_bitmask=row[2], source=row[3])


def is_token_in_cache(token: str, email: str) -> bool:
    entry = get_cached_token(email)
    if entry is None:
        return False
    return entry.token == token


def revoke_token(email: str) -> bool:
    conn = _connect()
    try:
        cursor = conn.execute("DELETE FROM tokens WHERE email = ?", (email,))
        conn.commit()
        removed = cursor.rowcount > 0
    finally:
        conn.close()
    if removed:
        audit.info(json.dumps({
            "audit": "token_revoked",
            "email": email,
            "timestamp": _iso(time.time()),
        }))
    return removed


def revoke_all_tokens() -> int:
    conn = _connect()
    try:
        rows = conn.execute("SELECT email FROM tokens").fetchall()
        conn.execute("DELETE FROM tokens")
        conn.commit()
    finally:
        conn.close()
    for (email,) in rows:
        audit.info(json.dumps({
            "audit": "token_revoked",
            "email": email,
            "timestamp": _iso(time.time()),
        }))
    return len(rows)


def list_tokens() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT email, groups_bitmask, created_at, expires_at, source FROM tokens "
            "WHERE expires_at > ?",
            (time.time(),),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "email": r[0],
            "groups_bitmask": r[1],
            "issued_at": r[2],
            "expires": r[3],
            "source": r[4],
        }
        for r in rows
    ]


def search_tokens(query: str) -> list[dict]:
    q = query.lower()
    return [t for t in list_tokens() if q in t["email"].lower()]


# ── Backup compat (called from main.py lifespan) ──────────────────────────


def save_backup() -> None:
    """No-op — SQLite file IS the persistent store."""
    pass


def load_backup() -> int:
    """Initialize DB and count active (non-expired) entries."""
    init_db()
    conn = _connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE expires_at > ?",
            (time.time(),),
        ).fetchone()[0]
    finally:
        conn.close()
    logger.info("token cache DB: %d active entries", count)
    return count
