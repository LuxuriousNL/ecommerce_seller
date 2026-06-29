"""Epic A2: organic channel seam + Meta/TikTok adapters (mocked)."""

from __future__ import annotations

import httpx

from adsuite.channels import organic as org
from adsuite.channels.organic import (
    DryRunOrganicChannel,
    MetaOrganicChannel,
    TikTokOrganicChannel,
    format_caption,
    make_channel,
    post_creative,
)
from adsuite.config import AdSettings
from adsuite.models import Creative

CREATIVE = Creative(slug="retro-tee", image_urls=["https://cdn/x.png"],
                    organic_caption="Catch the wave.", hashtags=["retro", "surf"])


def test_format_caption_includes_hashtags():
    cap = format_caption(CREATIVE)
    assert "Catch the wave." in cap and "#retro" in cap and "#surf" in cap


def test_dryrun_channel_when_no_creds():
    cfg = AdSettings()  # empty creds
    ch = make_channel("facebook", cfg)
    assert isinstance(ch, DryRunOrganicChannel)
    res = ch.post(CREATIVE)
    assert res.dry_run and res.ok and res.channel == "facebook"


def test_make_real_channel_when_creds_present():
    cfg = AdSettings(META_ACCESS_TOKEN="t", META_PAGE_ID="p", META_IG_USER_ID="ig",
                     TIKTOK_ACCESS_TOKEN="tk")
    assert isinstance(make_channel("facebook", cfg), MetaOrganicChannel)
    assert isinstance(make_channel("instagram", cfg), MetaOrganicChannel)
    assert isinstance(make_channel("tiktok", cfg), TikTokOrganicChannel)


class FakeHttp:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, data=None, json=None, headers=None):
        self.calls.append({"url": url, "data": data, "json": json, "headers": headers})
        return self._responses.pop(0)


def test_facebook_posts_photo():
    http = FakeHttp([httpx.Response(200, json={"id": "fb_1"})])
    ch = MetaOrganicChannel("tok", surface="facebook", page_id="123", http=http)
    res = ch.post(CREATIVE)
    assert res.ok and res.post_id == "fb_1"
    assert http.calls[0]["url"].endswith("/123/photos")
    assert http.calls[0]["data"]["url"] == "https://cdn/x.png"


def test_instagram_creates_then_publishes():
    http = FakeHttp([
        httpx.Response(200, json={"id": "creation_1"}),  # /media
        httpx.Response(200, json={"id": "ig_post_1"}),   # /media_publish
    ])
    ch = MetaOrganicChannel("tok", surface="instagram", ig_user_id="999", http=http)
    res = ch.post(CREATIVE)
    assert res.ok and res.post_id == "ig_post_1"
    assert http.calls[0]["url"].endswith("/999/media")
    assert http.calls[1]["url"].endswith("/999/media_publish")
    assert http.calls[1]["data"]["creation_id"] == "creation_1"


def test_tiktok_inits_post():
    http = FakeHttp([httpx.Response(200, json={"data": {"publish_id": "tt_1"}})])
    ch = TikTokOrganicChannel("tok", http=http)
    res = ch.post(CREATIVE)
    assert res.ok and res.post_id == "tt_1"
    assert http.calls[0]["json"]["media_type"] == "PHOTO"
    assert http.calls[0]["headers"]["Authorization"] == "Bearer tok"


def test_meta_requires_hosted_image():
    ch = MetaOrganicChannel("tok", surface="facebook", page_id="1")
    res = ch.post(Creative(slug="no-img"))
    assert not res.ok and "image_url" in res.error


def test_post_creative_to_multiple_channels_dryruns(monkeypatch):
    # No creds -> all dry-run.
    monkeypatch.setattr(org, "settings", AdSettings())
    results = post_creative(CREATIVE, ["facebook", "instagram", "tiktok"])
    assert set(results) == {"facebook", "instagram", "tiktok"}
    assert all(r.dry_run for r in results.values())
