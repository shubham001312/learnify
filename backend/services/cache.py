"""
Simple in-memory caching layer with TTL and version-based invalidation.

For serverless (Vercel), this resets on cold start — acceptable for MVP.
Replace with Redis for persistent caching in production.
"""

import hashlib
import json
import time
from typing import Any, Optional


_cache: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Optional[Any]:
    """Get a cached value. Returns None if expired or missing."""
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a cached value with TTL in seconds."""
    _cache[key] = (time.time() + ttl_seconds, value)


def invalidate(key: str) -> None:
    """Remove a specific cache entry."""
    _cache.pop(key, None)


def invalidate_pattern(pattern: str) -> int:
    """Remove all keys matching a prefix pattern. Returns count removed."""
    to_remove = [k for k in _cache if k.startswith(pattern)]
    for k in to_remove:
        _cache.pop(k, None)
    return len(to_remove)


def user_key(user_id: str, resource: str, version: int = 0) -> str:
    """Generate a cache key for a user resource."""
    return f"learnify:user:{user_id}:{resource}:v{version}"


def search_key(params: dict) -> str:
    """Generate a deterministic cache key from search parameters."""
    raw = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"learnify:search:{h}"


def clear_all() -> int:
    """Clear all cached entries. Returns count removed."""
    count = len(_cache)
    _cache.clear()
    return count
