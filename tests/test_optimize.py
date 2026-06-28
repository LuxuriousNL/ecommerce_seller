"""Phase 2 optimizer tests — fake Anthropic client, no API calls."""

from __future__ import annotations

from types import SimpleNamespace

from etsyshop.config import settings
from etsyshop.models import Design, OptimizedListing, ProductTemplate
from etsyshop.optimize import normalize_listing, optimize_listing

TEMPLATE = ProductTemplate(name="Tee", blueprint_id=6, print_provider_id=99)
DESIGN = Design(slug="sunset", theme="retro surf", keywords=["retro", "surf"])


def test_normalize_enforces_etsy_limits():
    raw = OptimizedListing(
        title="X" * 200,
        tags=["Retro Sunset!!"] * 5 + [f"uniq {i}" for i in range(20)],
        description="  hello  ",
        materials=["cotton"] * 20,
    )
    n = normalize_listing(raw)
    assert len(n.title) == 140
    assert len(n.tags) == 13
    assert len(set(n.tags)) == 13  # deduped
    assert all(len(t) <= 20 for t in n.tags)
    assert all(t == t.lower() and "!" not in t for t in n.tags)
    assert n.description == "hello"
    assert len(n.materials) == 13


class FakeMessages:
    def __init__(self, listing):
        self._listing = listing
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(parsed_output=self._listing)


class FakeAnthropic:
    def __init__(self, listing):
        self.messages = FakeMessages(listing)


def test_optimize_listing_normalizes_model_output(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    raw = OptimizedListing(
        title="Y" * 180,
        tags=[f"keyword phrase {i}" for i in range(20)],
        description="desc",
        materials=[],
    )
    client = FakeAnthropic(raw)
    result = optimize_listing(DESIGN, TEMPLATE, client=client)

    assert len(result.title) == 140
    assert len(result.tags) == 13
    # The prompt carried the design's theme + product type to the model.
    sent = client.messages.kwargs
    assert sent["model"] == settings.anthropic_model
    assert sent["output_format"] is OptimizedListing
    user_msg = sent["messages"][0]["content"]
    assert "retro surf" in user_msg and "Tee" in user_msg
