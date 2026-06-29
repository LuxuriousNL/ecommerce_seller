"""Epic S (S.7): adsuite <-> Shopify integration — Shopping/PMax + pixel->ledger."""

from __future__ import annotations

import httpx

from adsuite.channels.paid import GoogleAdsChannel, launch_shopping
from adsuite.config import AdSettings
from adsuite.models import Campaign, Creative, Metrics
from etsyshop.profit import ad_components_from_metrics, build_ledger


class FakeHttp:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, data=None):
        self.calls.append({"url": url, "json": json})
        return self._responses.pop(0)


def test_google_search_is_default():
    http = FakeHttp([httpx.Response(200, json={"mutateOperationResponses": []})])
    ch = GoogleAdsChannel("dev", "123", access_token="at", http=http)
    ch.create_campaign(Campaign(name="c", channel="google_ads", objective="traffic"),
                       Creative(slug="x"))
    ops = http.calls[0]["json"]["mutateOperations"]
    assert ops[1]["campaignOperation"]["create"]["advertisingChannelType"] == "SEARCH"


def test_google_pmax_for_shopping_objective():
    http = FakeHttp([httpx.Response(200, json={"mutateOperationResponses": []})])
    ch = GoogleAdsChannel("dev", "123", access_token="at", http=http)
    ch.create_campaign(Campaign(name="c", channel="google_ads", objective="pmax"),
                       Creative(slug="x"))
    create = http.calls[0]["json"]["mutateOperations"][1]["campaignOperation"]["create"]
    assert create["advertisingChannelType"] == "PERFORMANCE_MAX"
    assert "manualCpc" not in create  # PMax doesn't take manual CPC


def test_launch_shopping_dryruns_without_creds(monkeypatch):
    from adsuite.channels import paid as paid_mod
    monkeypatch.setattr(paid_mod, "settings", AdSettings())
    res = launch_shopping(Creative(slug="retro", landing_url="https://shop"),
                          daily_budget=5.0, name="retro-shopping", store_url="https://shop")
    assert "google_ads" in res and res["google_ads"].dry_run


def test_ad_components_from_metrics_feeds_ledger():
    metrics = {"retro-tee": Metrics(spend=20.0, revenue=120.0, conversions=6)}
    ad_spend, revenue, units = ad_components_from_metrics(metrics)
    assert ad_spend["retro-tee"] == 20.0 and revenue["retro-tee"] == 120.0 and units["retro-tee"] == 6
    # those components flow straight into the profit ledger
    ledger = build_ledger(revenue_by_key=revenue, units_by_key=units, ad_spend_by_key=ad_spend)
    p = ledger["retro-tee"]
    assert p.ad_spend == 20.0 and p.revenue == 120.0 and p.net_profit < 120.0
