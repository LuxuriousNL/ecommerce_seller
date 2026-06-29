"""E5.6 print-standard normalization."""

from __future__ import annotations

import io

import pytest

from etsyshop.imagestd import normalize_print

Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")


def _png(mode: str = "RGB", size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, "red").save(buf, format="PNG")
    return buf.getvalue()


def test_normalize_embeds_dpi():
    out, ok = normalize_print(_png(), dpi=300)
    assert ok
    img = Image.open(io.BytesIO(out))
    dpi = img.info.get("dpi")  # stored as px/meter, round-trips ~299.999
    assert dpi == pytest.approx((300, 300), abs=0.1)


def test_normalize_converts_palette_to_rgba():
    out, ok = normalize_print(_png(mode="P"), ensure_rgba=True)
    assert ok
    assert Image.open(io.BytesIO(out)).mode in ("RGB", "RGBA")


def test_normalize_passthrough_on_non_image():
    out, ok = normalize_print(b"not an image")
    assert ok is False and out == b"not an image"
