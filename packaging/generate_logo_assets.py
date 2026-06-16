"""Generate Omnivert's production logo assets from the master glyph path.

The brand glyph is a blurred multi-gradient SVG (``frontend/public/favicon.svg``) that looks
great large but muddies at icon sizes. This derives crisp raster assets from the glyph's
silhouette: a flat fill for small/icon use and a gradient fill for large/display use — the
direction chosen during planning (flat icons, gradient display, horizontal wordmark lockup).

Pure-Python (``svg.path`` + Pillow + numpy), so it runs without native SVG libraries. Assets
are generated once and committed; this script is kept for reproducibility, not run in CI.

Run:  python packaging/generate_logo_assets.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from svg.path import parse_path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
PACKAGING = ROOT / "packaging"
ASSETS = ROOT / "assets"

# Master glyph silhouette (viewBox 48 x 46), taken from favicon.svg's outer path.
GLYPH_D = (
    "M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287"
    "c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456"
    "-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48"
    " 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"
)
VB_W, VB_H = 48.0, 46.0

FLAT = (134, 59, 255)  # #863bff
GRAD_STOPS = [(0.0, (154, 85, 255)), (0.55, (126, 20, 255)), (1.0, (71, 191, 255))]
DARK_BG = (26, 16, 48)  # #1a1030
WORDMARK_FONT = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "seguisb.ttf"


def _glyph_mask(box: int, supersample: int = 4) -> Image.Image:
    """Return an L-mode alpha mask of the glyph, fit into a ``box``×``box`` square (aspect
    preserved, centered), anti-aliased via supersampling."""
    ss = box * supersample
    path = parse_path(GLYPH_D)
    scale = min(ss / VB_W, ss / VB_H)
    gw, gh = VB_W * scale, VB_H * scale
    ox, oy = (ss - gw) / 2, (ss - gh) / 2
    pts = []
    for seg in path:
        for i in range(49):
            p = seg.point(i / 48)
            pts.append((ox + p.real * scale, oy + p.imag * scale))
    mask = Image.new("L", (ss, ss), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.resize((box, box), Image.LANCZOS)


def _gradient(size: int) -> Image.Image:
    """Diagonal (top-left → bottom-right) gradient RGB image of the brand stops."""
    yy, xx = np.mgrid[0:size, 0:size]
    t = (xx + yy) / (2 * (size - 1))
    out = np.zeros((size, size, 3), dtype=np.float64)
    for c in range(3):
        xs = [s[0] for s in GRAD_STOPS]
        ys = [s[1][c] for s in GRAD_STOPS]
        out[..., c] = np.interp(t, xs, ys)
    return Image.fromarray(out.astype("uint8"), "RGB")


def _glyph(box: int, *, gradient: bool, pad_frac: float = 0.06) -> Image.Image:
    """Transparent RGBA glyph tile of ``box``px, flat or gradient-filled, with padding."""
    inner = round(box * (1 - 2 * pad_frac))
    mask = _glyph_mask(inner)
    fill = _gradient(inner) if gradient else Image.new("RGB", (inner, inner), FLAT)
    fill.putalpha(mask)
    tile = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    off = (box - inner) // 2
    tile.paste(fill, (off, off), fill)
    return tile


def _on_bg(glyph: Image.Image, size: int, bg) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg + (255,) if len(bg) == 3 else bg)
    canvas.alpha_composite(glyph)
    return canvas.convert("RGB")


def _wordmark(text: str, height: int, color) -> Image.Image:
    font = ImageFont.truetype(str(WORDMARK_FONT), height)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    img = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-l + 2, -t + 2), text, font=font, fill=color + (255,))
    return img


def _lockup(out: Path, *, size, bg, glyph_grad, text_color, tagline_color=None):
    """Horizontal lockup: gradient glyph + 'Omnivert' wordmark (+ optional tagline), centered
    on a panel of ``size`` (w, h)."""
    w, h = size
    panel = Image.new("RGBA", (w, h), bg)
    g = round(h * 0.46)
    glyph = _glyph(g, gradient=glyph_grad, pad_frac=0.0)
    word = _wordmark("Omnivert", round(h * 0.30), text_color)
    tag = _wordmark("Convert anything to Markdown", round(h * 0.085), tagline_color) if tagline_color else None
    gap = round(h * 0.10)
    block_w = g + gap + word.width
    x0 = (w - block_w) // 2
    cy = h // 2 - (round(h * 0.05) if tag else 0)
    panel.alpha_composite(glyph, (x0, cy - g // 2))
    tx = x0 + g + gap
    panel.alpha_composite(word, (tx, cy - word.height // 2))
    if tag:
        panel.alpha_composite(tag, (tx + 2, cy + word.height // 2 + round(h * 0.04)))
    panel.convert("RGB").save(out)
    return out


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    # 1. Flat app icon (.ico) — crisp at every Windows size.
    master = _glyph(256, gradient=False)
    ico_sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    master.save(PACKAGING / "omnivert.ico", sizes=ico_sizes)

    # 2. Web favicon PNG fallback (flat, small) + maskable/apple tiles (gradient, large).
    _glyph(32, gradient=False).save(PUBLIC / "favicon.png")
    _on_bg(_glyph(180, gradient=True, pad_frac=0.14), 180, (245, 242, 255)).save(
        PUBLIC / "apple-touch-icon.png"
    )
    _on_bg(_glyph(512, gradient=True, pad_frac=0.22), 512, DARK_BG).save(
        PUBLIC / "logo-maskable-512.png"
    )

    # 3. README banner (light, self-contained) + GitHub social preview (dark).
    _lockup(
        ASSETS / "omnivert-banner.png",
        size=(1280, 320),
        bg=(245, 242, 255, 255),
        glyph_grad=True,
        text_color=(42, 16, 85),
        tagline_color=(110, 90, 160),
    )
    _lockup(
        ASSETS / "omnivert-social-preview.png",
        size=(1280, 640),
        bg=DARK_BG + (255,),
        glyph_grad=True,
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
