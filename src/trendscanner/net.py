"""Polite, robots-aware HTTP fetch. No aggressive crawling."""

from __future__ import annotations

import urllib.robotparser as robotparser
from urllib.parse import urlsplit

import httpx

DEFAULT_UA = "trendscanner/0.1 (+respectful bot; prefers RSS/official APIs)"


def robots_allowed(url: str, user_agent: str = DEFAULT_UA) -> bool:
    """Check robots.txt for `url`. If robots.txt is unreachable, default to allow."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{base}/robots.txt")
    try:
        rp.read()
    except Exception:  # noqa: BLE001 — no robots.txt reachable
        return True
    return rp.can_fetch(user_agent, url)


def polite_get(
    url: str,
    *,
    user_agent: str = DEFAULT_UA,
    timeout: float = 20.0,
    respect_robots: bool = True,
) -> bytes:
    """GET with a clear UA, honoring robots.txt. Raises if disallowed."""
    if respect_robots and not robots_allowed(url, user_agent):
        raise PermissionError(f"robots.txt disallows fetching {url}")
    resp = httpx.get(url, headers={"User-Agent": user_agent}, timeout=timeout,
                     follow_redirects=True)
    resp.raise_for_status()
    return resp.content
