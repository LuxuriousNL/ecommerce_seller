"""Claude-vision QC for generated artwork.

Automates the "human QC pass" the research insisted on: Claude inspects each
generated image and flags issues (garbled/unintended text, watermarks, possible
trademarks/logos, anatomy errors) so failing art is held back before upload.
"""

from __future__ import annotations

import base64

import anthropic
from pydantic import BaseModel, Field

from etsyshop.config import settings
from etsyshop.models import DesignBrief

# Claude vision accepts these raster types; SVG must be rasterized first.
QC_SUPPORTED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}

QC_SYSTEM = """\
You are a print-on-demand QA reviewer for an Etsy shop. Inspect the image and \
decide if it is ready to sell. Flag any of these as issues:
- unintended or garbled text, misspellings, or stray letters/glyphs;
- watermarks, signatures, or stock-photo marks;
- recognizable brand logos, franchise/film/game characters, celebrity \
likenesses, or sports marks (IP risk — not allowed);
- anatomy errors (extra fingers, malformed hands/faces), broken symmetry, or \
obvious AI artifacts;
- low quality, heavy noise, or muddy/cut-off composition.
Set passed=false if ANY serious issue is present. Be specific in `issues`."""


class QCResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    has_unintended_text: bool = False
    possible_trademark: bool = False
    notes: str = ""


def qc_image(
    image: bytes,
    brief: DesignBrief,
    *,
    mime: str = "image/png",
    client: anthropic.Anthropic | None = None,
) -> QCResult:
    """Review a generated image with Claude vision. Non-raster types pass with a note."""
    if mime not in QC_SUPPORTED_MIME:
        return QCResult(passed=True, notes=f"{mime} not visually QC'd (needs rasterization)")

    settings.require("anthropic_api_key")
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(image).decode()

    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=QC_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text",
                 "text": f"Intended design: {brief.subject} ({brief.style}). "
                         "Review it for sale-readiness."},
            ],
        }],
        output_format=QCResult,
    )
    return response.parsed_output
