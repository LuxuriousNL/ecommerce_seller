"""Image seam tests: providers, factory, Claude-vision QC, design orchestrator."""

from __future__ import annotations

import base64
from types import SimpleNamespace

import httpx

from etsyshop import imagegen
from etsyshop.config import settings
from etsyshop.design import create_design
from etsyshop.imagegen import (
    GeneratedImage,
    OpenAIImageProvider,
    RecraftImageProvider,
    is_vector_product,
    select_provider,
)
from etsyshop.imageqc import QCResult, qc_image
from etsyshop.models import DesignBrief

BRIEF = DesignBrief(subject="retro sunset surf", style="70s screenprint", palette="warm sunset")


def test_is_vector_product():
    assert is_vector_product("Halloween Sticker Sheet")
    assert is_vector_product("Unisex Tee")
    assert not is_vector_product("Ceramic Ornament")


def test_select_provider_modes(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "ok")
    monkeypatch.setattr(settings, "recraft_api_key", "rk")
    # auto: vector -> recraft, raster -> openai
    monkeypatch.setattr(settings, "image_provider", "auto")
    assert select_provider("Sticker").name == "recraft"
    assert select_provider("Poster").name == "openai"
    # explicit modes
    monkeypatch.setattr(settings, "image_provider", "openai")
    assert select_provider("Sticker").name == "openai"
    monkeypatch.setattr(settings, "image_provider", "manual")
    assert select_provider("Poster") is None


def test_select_provider_degrades_to_manual_without_keys(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "recraft_api_key", "")
    monkeypatch.setattr(settings, "image_provider", "auto")
    assert select_provider("Poster") is None


def test_openai_provider_decodes_b64(monkeypatch):
    captured = {}
    png = b"\x89PNG fake"

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, body=json, auth=headers["Authorization"])
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png).decode()}]})

    monkeypatch.setattr(imagegen.httpx, "post", fake_post)
    img = OpenAIImageProvider("sk-test").generate(BRIEF, size="1024x1024", transparent=True)
    assert img.data == png
    assert captured["url"].endswith("/images/generations")
    assert captured["body"]["background"] == "transparent"
    assert captured["auth"] == "Bearer sk-test"
    assert "retro sunset surf" in captured["body"]["prompt"]


def test_recraft_provider_fetches_url(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert json["style"] == "vector_illustration"
        return httpx.Response(200, json={"data": [{"url": "https://cdn/recraft/out.svg"}]})

    def fake_get(url, timeout=None):
        return httpx.Response(200, content=b"<svg></svg>")

    monkeypatch.setattr(imagegen.httpx, "post", fake_post)
    monkeypatch.setattr(imagegen.httpx, "get", fake_get)
    img = RecraftImageProvider("rk").generate(BRIEF)
    assert img.mime == "image/svg+xml" and img.ext == "svg"
    assert img.data == b"<svg></svg>"


# --- QC ---
class FakeAnthropic:
    def __init__(self, result):
        self._result = result
        self.captured = None

    @property
    def messages(self):
        client = self

        class M:
            def parse(self, **kw):
                client.captured = kw
                return SimpleNamespace(parsed_output=client._result)
        return M()


def test_qc_passes_clean_image(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    fake = FakeAnthropic(QCResult(passed=True))
    res = qc_image(b"\x89PNG", BRIEF, mime="image/png", client=fake)
    assert res.passed
    content = fake.captured["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"


def test_qc_skips_non_raster():
    res = qc_image(b"<svg/>", BRIEF, mime="image/svg+xml")
    assert res.passed and "rasteriz" in res.notes.lower()


# --- Orchestrator ---
class FakeProvider:
    name = "fake"

    def __init__(self, image=None, fail=False):
        self.image = image or GeneratedImage(b"\x89PNG data")
        self.fail = fail

    def generate(self, brief, *, size="1024x1024", transparent=True):
        if self.fail:
            raise RuntimeError("gen boom")
        return self.image


def test_create_design_manual_writes_brief(tmp_path, monkeypatch):
    # Force manual so the test never makes a real (billable) image API call,
    # regardless of OPENAI_API_KEY/RECRAFT_API_KEY in the environment.
    monkeypatch.setattr(settings, "image_provider", "manual")
    art = create_design("sunset", BRIEF, product_type="Poster",
                        provider=None, qc=False, brief_dir=tmp_path)
    assert art.status == "manual"
    assert art.path.read_text().startswith("Subject:")


def test_create_design_ready_then_qc_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    provider = FakeProvider()
    qc_client = FakeAnthropic(QCResult(passed=False, issues=["garbled text"]))
    art = create_design("x", BRIEF, provider=provider, qc=True,
                        qc_client=qc_client, art_dir=tmp_path)
    assert art.status == "qc_failed"
    assert art.path.exists() and art.qc.issues == ["garbled text"]

    ok = create_design("y", BRIEF, provider=FakeProvider(), qc=True,
                       qc_client=FakeAnthropic(QCResult(passed=True)), art_dir=tmp_path)
    assert ok.status == "ready"


def test_create_design_provider_error(tmp_path):
    art = create_design("z", BRIEF, provider=FakeProvider(fail=True), qc=False, art_dir=tmp_path)
    assert art.status == "error" and "boom" in art.error
