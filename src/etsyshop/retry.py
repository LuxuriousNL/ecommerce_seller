"""Shared retry policy for the HTTP clients (rate limits + transient errors)."""

from __future__ import annotations

import httpx

# 429 = rate limited; 5xx = transient server errors. Retry these.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def retry_delay(resp: httpx.Response, attempt: int, *, base: float = 0.5, cap: float = 30.0) -> float:
    """Honor Retry-After if present (seconds), else exponential backoff."""
    ra = resp.headers.get("Retry-After", "").strip()
    if ra.isdigit():
        return min(float(ra), cap)
    return min(base * (2 ** attempt), cap)
