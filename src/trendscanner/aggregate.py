"""Aggregate raw signals into ranked trending terms.

Tokenizes signal text into 1–3 word phrases, drops stopwords, and ranks by how
often a phrase recurs across signals (frequency = trend strength).
"""

from __future__ import annotations

import re
from collections import Counter

from trendscanner.models import TrendSignal

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "your",
    "you", "this", "that", "is", "are", "be", "best", "new", "how", "what", "why",
    "from", "by", "at", "it", "as", "we", "our", "my", "i", "get", "make", "now",
    "top", "these", "their", "they", "more", "most", "into", "out", "up", "all",
}


def extract_terms(text: str, *, ngram_max: int = 3) -> list[str]:
    """Content-word 1..ngram_max phrases from text."""
    words = [w for w in re.findall(r"[a-z0-9']+", text.lower())
             if w not in STOPWORDS and len(w) > 2]
    terms: list[str] = []
    for n in range(1, ngram_max + 1):
        for i in range(len(words) - n + 1):
            terms.append(" ".join(words[i:i + n]))
    return terms


def aggregate(
    signals: list[TrendSignal], *, top: int = 20, min_count: int = 2, ngram_max: int = 3
) -> list[TrendSignal]:
    """Rank recurring phrases across signals into aggregated trend signals."""
    counts: Counter[str] = Counter()
    score: Counter[str] = Counter()
    category: dict[str, str] = {}
    for sig in signals:
        for term in set(extract_terms(sig.term, ngram_max=ngram_max)):
            counts[term] += 1
            score[term] += sig.score
            category.setdefault(term, sig.category)

    ranked = sorted(
        (t for t, c in counts.items() if c >= min_count),
        key=lambda t: (counts[t], score[t]),
        reverse=True,
    )
    return [
        TrendSignal(source="aggregate", term=t, category=category[t], score=float(counts[t]))
        for t in ranked[:top]
    ]
