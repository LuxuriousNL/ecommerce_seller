"""Print-standard normalization (300 DPI, RGBA PNG).

Uses Pillow when available (the optional `[images]` extra); degrades to a
passthrough so the core pipeline never hard-depends on it.
"""

from __future__ import annotations

import io


def normalize_print(data: bytes, *, dpi: int = 300, ensure_rgba: bool = True) -> tuple[bytes, bool]:
    """Return (bytes, normalized?). Embeds DPI + RGBA PNG if Pillow is installed."""
    try:
        from PIL import Image
    except ImportError:
        return data, False
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:  # noqa: BLE001 — not a raster we can open
        return data, False

    if ensure_rgba and img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    out = io.BytesIO()
    img.save(out, format="PNG", dpi=(dpi, dpi))
    return out.getvalue(), True
