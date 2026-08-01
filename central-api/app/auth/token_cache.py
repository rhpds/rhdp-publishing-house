"""In-memory token cache with TTL eviction, audit logging, and encrypted backup."""
import base64
import hashlib
import json
import logging
import os
import threading
import time
from typing import NamedTuple, Optional

from cachetools import TTLCache
from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings

logger = logging.getLogger(__name__)
audit = logging.getLogger("ph.audit")


class CacheEntry(NamedTuple):
    token: str
    created_at: float
    groups_bitmask: int
    source: str


_cache: Optional[TTLCache] = None
_lock = threading.Lock()


def _get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        settings = get_settings()
        ttl = settings.api_key_ttl_days * 86400
        _cache = TTLCache(maxsize=10000, ttl=ttl)
    return _cache


def _fernet() -> Fernet:
    settings = get_settings()
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.ph_api_key.encode()).digest()
    )
    return Fernet(key)


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── Public API ──────────────────────────────────────────────────────────────


def cache_token(email: str, token: str, groups_bitmask: int, source: str) -> None:
    now = time.time()
    entry = CacheEntry(token=token, created_at=now, groups_bitmask=groups_bitmask, source=source)
    with _lock:
        _get_cache()[email] = entry
    audit.info(json.dumps({
        "audit": "token_issued",
        "email": email,
        "timestamp": _iso(now),
        "groups_bitmask": groups_bitmask,
        "source": source,
    }))


def get_cached_token(email: str) -> Optional[CacheEntry]:
    with _lock:
        return _get_cache().get(email)


def is_token_in_cache(token: str, email: str) -> bool:
    entry = get_cached_token(email)
    if entry is None:
        return False
    return entry.token == token


def revoke_token(email: str) -> bool:
    with _lock:
        cache = _get_cache()
        if email in cache:
            del cache[email]
            audit.info(json.dumps({
                "audit": "token_revoked",
                "email": email,
                "timestamp": _iso(time.time()),
            }))
            return True
    return False


def revoke_all_tokens() -> int:
    with _lock:
        cache = _get_cache()
        entries = list(cache.items())
        cache.clear()
    for email, _ in entries:
        audit.info(json.dumps({
            "audit": "token_revoked",
            "email": email,
            "timestamp": _iso(time.time()),
        }))
    return len(entries)


def list_tokens() -> list[dict]:
    with _lock:
        cache = _get_cache()
        items = list(cache.items())
    ttl = get_settings().api_key_ttl_days * 86400
    return [
        {
            "email": email,
            "groups_bitmask": entry.groups_bitmask,
            "issued_at": entry.created_at,
            "expires": entry.created_at + ttl,
            "source": entry.source,
        }
        for email, entry in items
    ]


def search_tokens(query: str) -> list[dict]:
    q = query.lower()
    return [t for t in list_tokens() if q in t["email"].lower()]


# ── Encrypted backup ───────────────────────────────────────────────────────


def save_backup() -> None:
    settings = get_settings()
    path = settings.token_cache_path
    with _lock:
        cache = _get_cache()
        items = list(cache.items())

    if not items:
        if os.path.exists(path):
            os.remove(path)
        return

    records = [
        {
            "email": email,
            "token": entry.token,
            "created_at": entry.created_at,
            "groups_bitmask": entry.groups_bitmask,
            "source": entry.source,
        }
        for email, entry in items
    ]

    try:
        encrypted = _fernet().encrypt(json.dumps(records).encode())
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(encrypted)
        logger.info("token cache backup saved: %d entries", len(records))
    except Exception as exc:
        logger.error("failed to save token cache backup: %s", exc)


def load_backup() -> int:
    settings = get_settings()
    path = settings.token_cache_path
    if not os.path.exists(path):
        logger.info("no token cache backup found at %s", path)
        return 0

    try:
        with open(path, "rb") as f:
            encrypted = f.read()
        decrypted = _fernet().decrypt(encrypted)
        records = json.loads(decrypted)
    except InvalidToken:
        logger.warning("token cache backup unreadable (API key changed?), starting fresh")
        return 0
    except Exception as exc:
        logger.error("failed to load token cache backup: %s", exc)
        return 0

    ttl = settings.api_key_ttl_days * 86400
    now = time.time()
    loaded = 0
    with _lock:
        cache = _get_cache()
        for rec in records:
            age = now - rec["created_at"]
            if age >= ttl:
                continue
            entry = CacheEntry(
                token=rec["token"],
                created_at=rec["created_at"],
                groups_bitmask=rec["groups_bitmask"],
                source=rec["source"],
            )
            cache[rec["email"]] = entry
            loaded += 1

    logger.info("token cache restored: %d/%d entries (expired %d)", loaded, len(records), len(records) - loaded)
    return loaded
