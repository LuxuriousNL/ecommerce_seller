"""Resolve Etsy categories (taxonomy_id) and map desired attributes to valid values.

Etsy's search query-matching scans category and attributes, which Printify's
publish flow leaves unset. These helpers turn human strings ("Ornaments",
"Occasion=Christmas") into the exact taxonomy_id / property_id / value_id Etsy
expects, validating values against the category's allowed set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class TaxonomyMatch:
    taxonomy_id: int
    name: str
    full_path: str


def flatten_nodes(nodes: list[dict], _path: tuple[str, ...] = ()) -> Iterator[TaxonomyMatch]:
    """Walk the seller-taxonomy tree yielding every node with its full path."""
    for node in nodes:
        name = node.get("name", "")
        path = _path + (name,)
        yield TaxonomyMatch(int(node["id"]), name, " > ".join(path))
        children = node.get("children") or []
        yield from flatten_nodes(children, path)


def resolve_taxonomy_id(nodes_response: dict, query: str) -> TaxonomyMatch | None:
    """Best taxonomy node for `query`. Prefers exact name, then deepest substring match."""
    q = query.strip().lower()
    matches = list(flatten_nodes(nodes_response.get("results") or []))

    exact = [m for m in matches if m.name.lower() == q]
    if exact:
        # Prefer the deepest exact match (most specific category).
        return max(exact, key=lambda m: m.full_path.count(">"))

    partial = [m for m in matches if q in m.name.lower()]
    if partial:
        return max(partial, key=lambda m: (m.full_path.count(">"), -len(m.name)))
    return None


@dataclass
class PropertyUpdate:
    property_id: int
    name: str
    value_ids: list[int]
    values: list[str]


def map_attributes(
    properties: list[dict], desired: dict[str, str]
) -> tuple[list[PropertyUpdate], list[str]]:
    """Map {attribute_name: value} onto a category's properties.

    Returns (updates, skipped) — skipped names are attributes the category
    doesn't support or whose value isn't in the allowed set.
    """
    by_name = {p.get("name", "").lower(): p for p in properties}
    updates: list[PropertyUpdate] = []
    skipped: list[str] = []

    for attr, want in desired.items():
        prop = by_name.get(attr.lower())
        if not prop:
            skipped.append(attr)
            continue
        match = next(
            (v for v in prop.get("possible_values") or []
             if v.get("name", "").lower() == want.strip().lower()),
            None,
        )
        if not match:
            skipped.append(attr)
            continue
        updates.append(
            PropertyUpdate(
                property_id=int(prop["property_id"]),
                name=prop.get("name", attr),
                value_ids=[int(match["value_id"])],
                values=[match["name"]],
            )
        )
    return updates, skipped
