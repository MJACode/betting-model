"""
Render the Signalbase app icon set from the brand mark's geometry.

THE SOURCE OF TRUTH is the @signalbasepicks X profile image
(mobile/assets/brand/x_avatar.jpg, fetched by .github/workflows/
fetch-brand-assets.yml and hash-verified against the worker's brand_assets
row). It is a 400px JPEG, which is too small and too lossy to ship as a
1024px App Store icon, so the mark is re-drawn here from its measured
geometry rather than upscaled:

    canvas 400, mark bbox 92..307 (216px = 54% of the side, centred)
    three full-width bars 48px thick, two 36px gaps
    left stem joins bars 1-2 (x 0..48), right stem joins bars 2-3 (x 168..216)

i.e. in units of the mark side M: bar = M * 48/216, gap = M * 36/216.
Colours are sampled from the same file (amber ground, near-black-navy ink);
the splash inverts them (amber mark on the banner's navy), matching the X
banner's palette.

    python -m scripts.render_brand_icons          # writes mobile/assets/*.png

Idempotent; commit the outputs. A native rebuild (mobile-build.yml) is needed
for the icon/splash to reach devices -- app.json assets are not OTA-able.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

AMBER = (0xF2, 0xB0, 0x1E)      # the mark's ground        #F2B01E
INK = (0x0B, 0x13, 0x20)        # the mark's S             #0B1320
NAVY = (0x0B, 0x12, 0x20)       # the banner's ground      #0B1220

BAR = 48 / 216
GAP = 36 / 216
MARK_FRACTION = 216 / 400

ASSETS = Path(__file__).resolve().parent.parent / "mobile" / "assets"


def draw_mark(draw: ImageDraw.ImageDraw, x0: float, y0: float, side: float,
              fill: tuple[int, int, int]) -> None:
    """The stepped S: three bars joined by alternating stems."""
    t, g = side * BAR, side * GAP
    x1 = x0 + side
    rows = [(y0, y0 + t), (y0 + t + g, y0 + 2 * t + g), (y0 + 2 * t + 2 * g, y0 + side)]
    for a, b in rows:
        draw.rectangle([x0, a, x1, b], fill=fill)
    draw.rectangle([x0, rows[0][1], x0 + t, rows[1][0]], fill=fill)          # left stem
    draw.rectangle([x1 - t, rows[1][1], x1, rows[2][0]], fill=fill)          # right stem


def render(side: int, bg: tuple[int, int, int] | None, ink: tuple[int, int, int],
           fraction: float = MARK_FRACTION) -> Image.Image:
    """Draw at 4x and downsample so the diagonal-free mark still gets clean edges."""
    s = side * 4
    mode = "RGBA" if bg is None else "RGB"
    im = Image.new(mode, (s, s), (0, 0, 0, 0) if bg is None else bg)
    m = s * fraction
    draw_mark(ImageDraw.Draw(im), (s - m) / 2, (s - m) / 2, m, ink)
    return im.resize((side, side), Image.LANCZOS)


def main() -> None:
    out = {
        # App Store / home screen icon: the avatar, exactly.
        "icon.png": render(1024, AMBER, INK),
        # Android adaptive foreground: transparent, mark kept inside the 66%
        # safe zone; app.json supplies the amber background.
        "adaptive-icon.png": render(1024, None, INK, fraction=0.44),
        # Splash (resizeMode contain on the navy background from app.json):
        # amber mark on navy, the banner's palette.
        "splash.png": render(2048, NAVY, AMBER, fraction=0.22),
        "favicon.png": render(48, AMBER, INK),
        # In-app mark (sign-in / onboarding): the icon at a screen-friendly size.
        "brand/mark.png": render(512, AMBER, INK),
    }
    for name, im in out.items():
        path = ASSETS / name
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, optimize=True)
        print(f"wrote {path.relative_to(ASSETS.parent.parent)} {im.size} {im.mode}")


if __name__ == "__main__":
    main()
