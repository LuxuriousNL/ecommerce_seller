"""V.1/V.2: preflight checks + safe smoke tests."""

from __future__ import annotations

from etsyshop.doctor import Check, run_checks, smoke_etsy, smoke_printify, smoke_shopify


def test_run_checks_covers_all_systems():
    checks = run_checks()
    systems = {c.system for c in checks}
    assert "etsy" in systems and "printify" in systems and "anthropic" in systems
    assert "shopify" in systems
    assert any(s.startswith("ads:") for s in systems)
    assert any(s.startswith("image:") for s in systems)
    assert all(isinstance(c, Check) for c in checks)


def test_run_checks_reflects_configured_creds(monkeypatch):
    from etsyshop import config as es_config
    monkeypatch.setattr(es_config.settings, "anthropic_api_key", "set")
    monkeypatch.setattr(es_config.settings, "openai_api_key", "")
    by_system = {c.system: c for c in run_checks()}
    assert by_system["anthropic"].ready is True
    assert by_system["image:openai"].ready is False


def test_smoke_printify_and_etsy_and_shopify():
    class FakePrintify:
        def list_shops(self):
            return [{"id": 1}, {"id": 2}]

    class FakeEtsy:
        def whoami(self):
            return {"user_id": 42}

    class FakeShopify:
        def create_product(self, **kw):
            return {"id": "gid://dry/Product/1"}

    ok, detail = smoke_printify(FakePrintify())
    assert ok and "2 shop" in detail

    ok, detail = smoke_etsy(FakeEtsy())
    assert ok and "42" in detail

    ok, detail = smoke_shopify(FakeShopify())
    assert ok and "reachable" in detail
