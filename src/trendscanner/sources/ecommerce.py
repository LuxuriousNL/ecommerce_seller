"""Ecommerce adapter via JSON-LD structured data (robots-aware).

Reads schema.org Product / ItemList JSON-LD that retailers publish for SEO —
machine-readable by design — to extract product/term names from "new" or
"bestseller" pages, instead of scraping rendered HTML.
"""

from __future__ import annotations

import json
import re
from typing import Iterator

from trendscanner.models import TrendSignal
from trendscanner.net import DEFAULT_UA, polite_get

_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def extract_jsonld(html: str) -> list:
    blocks = []
    for m in _SCRIPT_RE.finditer(html):
        try:
            blocks.append(json.loads(m.group(1).strip()))
        except json.JSONDecodeError:
            continue
    return blocks


def _names(node) -> Iterator[str]:
    if isinstance(node, list):
        for x in node:
            yield from _names(x)
    elif isinstance(node, dict):
        if "@graph" in node:
            yield from _names(node["@graph"])
        types = node.get("@type", "")
        types = types if isinstance(types, list) else [types]
        if "Product" in types and node.get("name"):
            yield str(node["name"])
        if "ItemList" in types:
            for el in node.get("itemListElement", []):
                item = el.get("item", el) if isinstance(el, dict) else el
                yield from _names(item)


def parse_jsonld_products(html: str, *, source: str,
                          category: str = "ecommerce") -> list[TrendSignal]:
    seen: set[str] = set()
    out: list[TrendSignal] = []
    for block in extract_jsonld(html):
        for name in _names(block):
            key = name.strip().lower()
            if name.strip() and key not in seen:
                seen.add(key)
                out.append(TrendSignal(source=source, term=name.strip(), category=category))
    return out


def fetch_ecommerce(url: str, *, source: str | None = None, category: str = "ecommerce",
                    user_agent: str = DEFAULT_UA) -> list[TrendSignal]:
    raw = polite_get(url, user_agent=user_agent)
    return parse_jsonld_products(raw.decode("utf-8", "ignore"),
                                 source=source or f"ecom:{url}", category=category)
