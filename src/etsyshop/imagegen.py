"""Pluggable image-generation providers (the seam).

Claude can't generate images, so artwork comes from a third-party model. This
exposes a provider protocol with OpenAI GPT Image (raster) and Recraft
(vector/SVG) implementations, plus a factory that picks one by product type and
config — degrading to manual (None) when no key is available.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx

from etsyshop.config import settings
from etsyshop.models import DesignBrief

VECTOR_KEYWORDS = ("sticker", "svg", "tee", "shirt", "t-shirt", "decal", "cut file", "vector")


@dataclass
class GeneratedImage:
    data: bytes
    mime: str = "image/png"
    ext: str = "png"


@runtime_checkable
class ImageProvider(Protocol):
    name: str

    def generate(self, brief: DesignBrief, *, size: str = "1024x1024",
                 transparent: bool = True) -> GeneratedImage: ...


def is_vector_product(product_type: str) -> bool:
    t = (product_type or "").lower()
    return any(k in t for k in VECTOR_KEYWORDS)


class OpenAIImageProvider:
    """OpenAI GPT Image (raster). Strong prompt-following, transparent backgrounds."""

    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-image-1",
                 base_url: str = "https://api.openai.com/v1", timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def generate(self, brief: DesignBrief, *, size: str = "1024x1024",
                 transparent: bool = True) -> GeneratedImage:
        body: dict = {"model": self.model, "prompt": brief.to_prompt(), "size": size, "n": 1}
        if transparent:
            body["background"] = "transparent"
        resp = httpx.post(
            f"{self.base_url}/images/generations",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body, timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI image error {resp.status_code}: {resp.text[:200]}")
        item = resp.json()["data"][0]
        if item.get("b64_json"):
            return GeneratedImage(base64.b64decode(item["b64_json"]))
        if item.get("url"):
            return GeneratedImage(httpx.get(item["url"], timeout=self.timeout).content)
        raise RuntimeError("OpenAI image response had neither b64_json nor url.")


class RecraftImageProvider:
    """Recraft (vector/SVG-capable). Best for stickers, cut files, simple tee art."""

    name = "recraft"

    def __init__(self, api_key: str, model: str = "recraftv3",
                 style: str = "vector_illustration",
                 base_url: str = "https://external.api.recraft.ai/v1", timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.style = style
        self.base_url = base_url
        self.timeout = timeout

    def generate(self, brief: DesignBrief, *, size: str = "1024x1024",
                 transparent: bool = True) -> GeneratedImage:
        body = {"prompt": brief.to_prompt(), "style": self.style, "size": size, "model": self.model}
        resp = httpx.post(
            f"{self.base_url}/images/generations",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body, timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Recraft error {resp.status_code}: {resp.text[:200]}")
        item = resp.json()["data"][0]
        url = item.get("url")
        if url:
            content = httpx.get(url, timeout=self.timeout).content
            if url.lower().endswith(".svg"):
                return GeneratedImage(content, mime="image/svg+xml", ext="svg")
            return GeneratedImage(content)
        if item.get("b64_json"):
            return GeneratedImage(base64.b64decode(item["b64_json"]))
        raise RuntimeError("Recraft response had neither url nor b64_json.")


def select_provider(product_type: str = "") -> ImageProvider | None:
    """Pick a provider by config + product type. None => manual (write brief only)."""
    mode = (settings.image_provider or "auto").lower()
    if mode == "manual":
        return None

    def openai() -> ImageProvider | None:
        return OpenAIImageProvider(settings.openai_api_key) if settings.openai_api_key else None

    def recraft() -> ImageProvider | None:
        return RecraftImageProvider(settings.recraft_api_key) if settings.recraft_api_key else None

    if mode == "openai":
        return openai()
    if mode == "recraft":
        return recraft()

    # auto: vector products prefer Recraft; otherwise OpenAI; then whatever exists.
    if is_vector_product(product_type) and settings.recraft_api_key:
        return recraft()
    return openai() or recraft()
