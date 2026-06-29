"""Summarize adsuite experiments/campaigns for a quick report."""

from __future__ import annotations

from adsuite.store import ExperimentRecord


def build_report(experiments: dict[str, ExperimentRecord]) -> list[dict]:
    rows = []
    for slug, rec in experiments.items():
        rows.append({
            "slug": slug,
            "status": rec.status,
            "products": f"{rec.variant_a_product} vs {rec.variant_b_product}",
            "winner": rec.winner or "-",
            "campaigns": sum(len(v) for v in rec.campaigns.values()),
            "channels": ",".join(rec.channels),
        })
    rows.sort(key=lambda r: r["slug"])
    return rows
