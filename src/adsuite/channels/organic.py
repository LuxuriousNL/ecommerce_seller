"""Organic posting adapters: Facebook, Instagram, TikTok.

Each implements `post(creative) -> PostResult`. Without credentials the factory
returns a DryRun channel so the whole flow runs offline. Request shapes follow
the Meta Graph API and TikTok Content Posting API and are mock-tested.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from adsuite.config import AdSettings, channel_available, settings
from adsuite.models import Creative, PostResult

GRAPH = "https://graph.facebook.com/v21.0"
TIKTOK_INIT = "https://open.tiktokapis.com/v2/post/publish/content/init/"


def _check(resp) -> None:
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")


def format_caption(creative: Creative) -> str:
    tags = " ".join(f"#{h}" for h in creative.hashtags)
    return f"{creative.organic_caption}\n\n{tags}".strip()


@runtime_checkable
class OrganicChannel(Protocol):
    name: str

    def post(self, creative: Creative) -> PostResult: ...


class DryRunOrganicChannel:
    def __init__(self, name: str):
        self.name = name

    def post(self, creative: Creative) -> PostResult:
        return PostResult(ok=True, dry_run=True, channel=self.name, url="(dry-run)")


class MetaOrganicChannel:
    """Facebook Page photo post, or Instagram media create+publish."""

    def __init__(self, access_token: str, *, surface: str, page_id: str = "",
                 ig_user_id: str = "", http=httpx):
        self.name = surface  # "facebook" | "instagram"
        self.access_token = access_token
        self.page_id = page_id
        self.ig_user_id = ig_user_id
        self._http = http

    def post(self, creative: Creative) -> PostResult:
        if not creative.image_urls:
            return PostResult(ok=False, channel=self.name,
                              error="organic posting needs a hosted image_url")
        image_url = creative.image_urls[0]
        caption = format_caption(creative)
        try:
            if self.name == "facebook":
                r = self._http.post(f"{GRAPH}/{self.page_id}/photos",
                                    data={"url": image_url, "caption": caption,
                                          "access_token": self.access_token})
                _check(r)
                return PostResult(ok=True, channel=self.name, post_id=str(r.json().get("id")))
            # instagram: create container then publish
            c = self._http.post(f"{GRAPH}/{self.ig_user_id}/media",
                                data={"image_url": image_url, "caption": caption,
                                      "access_token": self.access_token})
            _check(c)
            creation_id = c.json()["id"]
            p = self._http.post(f"{GRAPH}/{self.ig_user_id}/media_publish",
                                data={"creation_id": creation_id,
                                      "access_token": self.access_token})
            _check(p)
            return PostResult(ok=True, channel=self.name, post_id=str(p.json().get("id")))
        except Exception as exc:  # noqa: BLE001
            return PostResult(ok=False, channel=self.name, error=str(exc))


class TikTokOrganicChannel:
    """TikTok Content Posting API (photo). Inits a post; may land as a draft."""

    name = "tiktok"

    def __init__(self, access_token: str, http=httpx):
        self.access_token = access_token
        self._http = http

    def post(self, creative: Creative) -> PostResult:
        if not creative.image_urls:
            return PostResult(ok=False, channel=self.name, error="tiktok needs a hosted image_url")
        body = {
            "post_info": {"title": creative.organic_caption[:90] or creative.slug,
                          "description": format_caption(creative)},
            "source_info": {"source": "PULL_FROM_URL",
                            "photo_images": creative.image_urls,
                            "photo_cover_index": 0},
            "post_mode": "MEDIA_UPLOAD",  # to drafts; DIRECT_POST needs audited app
            "media_type": "PHOTO",
        }
        try:
            r = self._http.post(TIKTOK_INIT, json=body,
                                headers={"Authorization": f"Bearer {self.access_token}",
                                         "Content-Type": "application/json"})
            _check(r)
            publish_id = (r.json().get("data") or {}).get("publish_id")
            return PostResult(ok=True, channel=self.name, post_id=str(publish_id))
        except Exception as exc:  # noqa: BLE001
            return PostResult(ok=False, channel=self.name, error=str(exc))


def make_channel(name: str, cfg: AdSettings | None = None) -> OrganicChannel:
    """Real adapter if credentials exist, else a dry-run channel."""
    cfg = cfg or settings
    if not channel_available(name, cfg):
        return DryRunOrganicChannel(name)
    if name == "facebook":
        return MetaOrganicChannel(cfg.meta_access_token, surface="facebook", page_id=cfg.meta_page_id)
    if name == "instagram":
        return MetaOrganicChannel(cfg.meta_access_token, surface="instagram",
                                  ig_user_id=cfg.meta_ig_user_id)
    if name == "tiktok":
        return TikTokOrganicChannel(cfg.tiktok_access_token)
    return DryRunOrganicChannel(name)


def post_creative(
    creative: Creative,
    channels: list[str],
    *,
    cfg: AdSettings | None = None,
) -> dict[str, PostResult]:
    """Post one creative to the named organic channels."""
    return {name: make_channel(name, cfg).post(creative) for name in channels}
