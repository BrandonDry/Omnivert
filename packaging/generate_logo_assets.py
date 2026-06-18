"""Generate Omnivert's production logo assets from the master glyph definition.

The brand glyph is an original "converge arrow" mark — several inputs converging into a
single rightward arrow — reflecting Omnivert's purpose of converting anything into one
Markdown output. ``frontend/public/favicon.svg`` is the hand-authored source of truth; this
script reproduces the exact same mark as committed raster assets (web icons, the Windows
``.ico``, and the README/social lockups).

Pure-Python (Pillow + numpy), so it runs without native SVG libraries: the glyph is a small
set of rounded strokes on a rounded gradient tile, drawn directly with Pillow primitives and
anti-aliased via supersampling.

Assets are generated once and committed; this script is kept for reproducibility, not run in
CI. Keep ``GLYPH_STROKES`` / ``TILE`` in sync with ``favicon.svg`` if the mark changes.

Run:  python packaging/generate_logo_assets.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
PACKAGING = ROOT / "packaging"
ASSETS = ROOT / "assets"

# --- Master mark (viewBox 48 x 48), mirrors frontend/public/favicon.svg ---------------
# Rounded gradient tile + white "converge arrow": three left-aligned rungs feeding a
# rightward chevron. Coordinates are in the 48-unit viewBox; everything scales from here.
VB = 48.0
TILE = dict(x=2.0, y=2.0, w=44.0, h=44.0, r=11.0)
STROKE_W = 3.2  # in viewBox units
GLYPH_STROKES = [
    [(13, 16), (22, 16)],            # top rung
    [(13, 24), (30, 24)],            # middle rung (longest)
    [(13, 32), (22, 32)],            # bottom rung
    [(27, 17), (34, 24), (27, 31)],  # arrowhead chevron
]

GRAD_STOPS = [(0.0, (155, 83, 255)), (0.55, (126, 20, 255)), (1.0, (71, 191, 255))]  # 9b53ff→7e14ff→47bfff
DARK_BG = (26, 17, 46)  # #1a112e
LIGHT_BG = (245, 242, 255)
# Brand wordmark font, with cross-platform fallbacks so the script runs off-Windows too.
_FONT_CANDIDATES = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "seguisb.ttf",  # Segoe UI Semibold
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def _gradient(size: int) -> Image.Image:
    """Diagonal (top-left → bottom-right) gradient RGB image of the brand stops."""
    yy, xx = np.mgrid[0:size, 0:size]
    t = (xx + yy) / (2 * (size - 1))
    out = np.zeros((size, size, 3), dtype=np.float64)
    xs = [s[0] for s in GRAD_STOPS]
    for c in range(3):
        out[..., c] = np.interp(t, xs, [s[1][c] for s in GRAD_STOPS])
    return Image.fromarray(out.astype("uint8"), "RGB")


def _stroke(draw: ImageDraw.ImageDraw, pts, width: float, fill) -> None:
    """Polyline with round caps and joins (Pillow squares both, so add discs by hand)."""
    ipts = [(round(x), round(y)) for x, y in pts]
    draw.line(ipts, fill=fill, width=round(width))
    r = width / 2.0
    for x, y in ipts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def tile(box: int, *, full_bleed: bool = False, supersample: int = 4) -> Image.Image:
    """Render the mark into a ``box``×``box`` RGBA tile.

    ``full_bleed`` fills the whole square (for maskable icons) and insets the glyph into a
    safe zone; otherwise a rounded tile is drawn on a transparent background.
    """
    ss = box * supersample
    s = ss / VB  # viewBox → pixel scale
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    grad = _gradient(ss)

    bg_mask = Image.new("L", (ss, ss), 0)
    bd = ImageDraw.Draw(bg_mask)
    if full_bleed:
        bd.rectangle((0, 0, ss, ss), fill=255)
    else:
        bd.rounded_rectangle(
            (TILE["x"] * s, TILE["y"] * s, (TILE["x"] + TILE["w"]) * s, (TILE["y"] + TILE["h"]) * s),
            radius=TILE["r"] * s,
            fill=255,
        )
    img.paste(grad, (0, 0), bg_mask)

    # Glyph layer (optionally inset to a safe zone for maskable icons).
    inset = 0.62 if full_bleed else 1.0
    cx = ss / 2.0
    gl = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    for poly in GLYPH_STROKES:
        pts = [((x * s - cx) * inset + cx, (y * s - cx) * inset + cx) for x, y in poly]
        _stroke(gd, pts, STROKE_W * s * inset, (255, 255, 255, 255))
    img.alpha_composite(gl)

    return img.resize((box, box), Image.LANCZOS)


def _on_bg(glyph: Image.Image, size: int, bg) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg + (255,) if len(bg) == 3 else bg)
    canvas.alpha_composite(glyph)
    return canvas.convert("RGB")


def _font(height: int) -> ImageFont.FreeTypeFont:
    for cand in _FONT_CANDIDATES:
        if cand.exists():
            return ImageFont.truetype(str(cand), height)
    raise FileNotFoundError("No wordmark font found; install Segoe UI or DejaVu Sans.")


def _wordmark(text: str, height: int, color) -> Image.Image:
    font = _font(height)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    img = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-l + 2, -t + 2), text, font=font, fill=color + (255,))
    return img


def _lockup(out: Path, *, size, bg, text_color, tagline_color) -> Path:
    """Horizontal lockup: gradient tile + 'Omnivert' wordmark + tagline.

    The block is composed at native sizes then uniformly scaled to fit the panel's safe
    area and centered, so it never clips regardless of the wordmark font's metrics.
    """
    w, h = size
    panel = Image.new("RGBA", (w, h), bg)

    g = round(h * 0.50)
    glyph = tile(g)
    word = _wordmark("Omnivert", round(h * 0.30), text_color)
    tag = _wordmark("Convert anything to Markdown", round(h * 0.095), tagline_color)
    gap = round(h * 0.10)
    tgap = round(h * 0.04)

    bw = g + gap + max(word.width, tag.width)
    bh = max(g, word.height + tgap + tag.height)
    block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    block.alpha_composite(glyph, (0, (bh - g) // 2))
    tx = g + gap
    ty = (bh - (word.height + tgap + tag.height)) // 2
    block.alpha_composite(word, (tx, ty))
    block.alpha_composite(tag, (tx + 2, ty + word.height + tgap))

    scale = min(w * 0.88 / bw, h * 0.80 / bh)
    if scale < 1.0:
        block = block.resize((round(bw * scale), round(bh * scale)), Image.LANCZOS)
    panel.alpha_composite(block, ((w - block.width) // 2, (h - block.height) // 2))
    panel.convert("RGB").save(out)
    return out


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    # 1. Windows app icon (.ico) — crisp at every size.
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    tile(256).save(
        PACKAGING / "omnivert.ico", sizes=[(s, s) for s in ico_sizes]
    )

    # 2. Web favicon PNG fallback + apple-touch + maskable (full-bleed safe zone).
    tile(32).save(PUBLIC / "favicon.png")
    tile(180).save(PUBLIC / "apple-touch-icon.png")
    tile(512, full_bleed=True).save(PUBLIC / "logo-maskable-512.png")

    # 3. README banner (light) + GitHub social preview (dark).
    _lockup(
        ASSETS / "omnivert-banner.png",
        size=(1280, 320),
        bg=LIGHT_BG + (255,),
        text_color=(42, 16, 85),
        tagline_color=(110, 90, 160),
    )
    _lockup(
        ASSETS / "omnivert-social-preview.png",
        size=(1280, 640),
        bg=DARK_BG + (255,),
        text_color=(255, 255, 255),
        tagline_color=(185, 163, 239),
    )

    print("Wrote:")
    for p in (
        PACKAGING / "omnivert.ico",
        PUBLIC / "favicon.png",
        PUBLIC / "apple-touch-icon.png",
        PUBLIC / "logo-maskable-512.png",
        ASSETS / "omnivert-banner.png",
        ASSETS / "omnivert-social-preview.png",
    ):
        print(" ", p.relative_to(ROOT), "-", p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
