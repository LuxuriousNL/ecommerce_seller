"""Profit gating: only spin up a dedicated store for a validated niche.

Consumes the etsyshop profit brain's decisions — a niche earns its own store
once it has at least one product the brain says to `scale` (profitable winner).
"""

from __future__ import annotations


def count_scalers(decisions) -> int:
    return sum(1 for d in decisions if getattr(d, "action", "") == "scale")


def qualifies_for_store(decisions, *, min_scalers: int = 1) -> bool:
    return count_scalers(decisions) >= min_scalers


def gate_store_creation(niche_slug: str, decisions, *, min_scalers: int = 1) -> tuple[bool, str]:
    """Decide whether to create a dedicated store for the niche, with a reason."""
    n = count_scalers(decisions)
    if n >= min_scalers:
        return True, f"{niche_slug}: {n} scaling product(s) — provision a store"
    return False, f"{niche_slug}: {n} scaling product(s) (< {min_scalers}) — hold"
