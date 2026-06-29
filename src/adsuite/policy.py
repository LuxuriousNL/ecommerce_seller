"""Ad-copy policy guardrails: prohibited claims + required disclosure.

Surfaced before publish so risky copy is flagged rather than silently shipped.
Not legal advice — a first-line filter for obvious platform/ASA/FTC issues.
"""

from __future__ import annotations

PROHIBITED_CLAIMS = (
    "guarantee", "guaranteed", "risk-free", "cure", "miracle", "clinically proven",
    "fda approved", "100% effective", "best in the world", "#1", "no.1", "lose weight fast",
)


def check_copy(text: str, *, paid: bool = False) -> list[str]:
    """Return policy issues for a piece of copy (empty = clean)."""
    issues: list[str] = []
    low = text.lower()
    for term in PROHIBITED_CLAIMS:
        if term in low:
            issues.append(f"prohibited claim: '{term}'")
    if paid and text.strip():
        disclosed = low.startswith("ad.") or "#ad" in low or "sponsored" in low
        if not disclosed:
            issues.append("paid copy missing ad disclosure")
    return issues


def review_creative(creative) -> list[str]:
    """Review a Creative's organic + paid copy before publishing."""
    issues = check_copy(creative.organic_caption, paid=False)
    if creative.paid_headline:
        issues += check_copy(creative.paid_headline, paid=False)
    if creative.paid_primary_text:
        issues += check_copy(creative.paid_primary_text, paid=True)
    return issues
