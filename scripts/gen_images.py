"""Learnify — raster asset generator (Pillow).

Regenerates the PWA icon set and the social/OG share card from
`public/assets/logo.jpeg`, so the branding can never drift out of sync
with the source artwork.

    & .\\.venv\\Scripts\\python.exe scripts\\gen_images.py

Outputs (all under public/assets):
    icon-192.png            PWA icon
    icon-512.png            PWA icon
    icon-maskable-512.png   Android maskable (content inside the 80% safe zone)
    apple-touch-icon.png    180x180, iOS (no transparency — iOS applies its own mask)
    og-cover.png            1200x630 social share card
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "public" / "assets"
LOGO = ASSETS / "logo.jpeg"

# Bounding box of the logo *mark* (cap + book) measured from the source art.
# The "Learnify" wordmark sits below y=470 and is deliberately excluded: at
# 192px it would be unreadable mush.
MARK_BOX = (189, 107, 533, 442)

FONTS = Path("C:/Windows/Fonts")
F_HEAD = FONTS / "bahnschrift.ttf"
F_BOLD = FONTS / "segoeuib.ttf"
F_BODY = FONTS / "segoeui.ttf"

BRAND_TEXT = "#0f172a"   # --text
BRAND_TEAL = "#0ea5a4"   # --accent / --teal
BRAND_GOLD = "#e0a526"   # --gold
BRAND_SOFT = "#f6f7f9"   # --bg-soft


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def logo_mark() -> Image.Image:
    """Crop the logo mark and knock the white background out to alpha.

    A plain "every white pixel becomes transparent" pass would punch holes in
    the lightbulb and the page highlights, so the white is removed by flooding
    *inward from the corners* — only background white disappears.
    """
    im = Image.open(LOGO).convert("RGBA").crop(MARK_BOX)
    w, h = im.size

    # Flood from a ring of points just outside the art on all four sides.
    probe = im.copy()
    bg = (255, 0, 255, 255)
    seeds = []
    step = max(1, w // 40)
    for x in range(0, w, step):
        seeds += [(x, 0), (x, h - 1)]
    for y in range(0, h, step):
        seeds += [(0, y), (w - 1, y)]
    for sx, sy in seeds:
        px = probe.getpixel((sx, sy))
        if px[0] > 238 and px[1] > 238 and px[2] > 238:
            ImageDraw.floodfill(probe, (sx, sy), bg, thresh=26)

    # Alpha = wherever the flood marker reached.
    alpha = Image.new("L", (w, h), 255)
    p = probe.load()
    a = alpha.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = p[x, y]
            if (r, g, b) == (255, 0, 255):
                a[x, y] = 0

    # Feather 1px so the cut edge does not look bitten.
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))
    im.putalpha(alpha)
    return im


def fit(mark: Image.Image, box: int, fill: float) -> Image.Image:
    """Scale `mark` so its longest side is `box * fill`, keeping aspect."""
    longest = max(mark.size)
    target = int(round(box * fill))
    if target < 1 or longest < 1:
        return mark
    scale = target / longest
    return mark.resize((max(1, int(mark.width * scale)),
                        max(1, int(mark.height * scale))), Image.LANCZOS)


def paste_center(canvas: Image.Image, art: Image.Image) -> None:
    canvas.alpha_composite(
        art, ((canvas.width - art.width) // 2, (canvas.height - art.height) // 2))


def make_icon(size: int, mark: Image.Image, fill: float,
              bg=(255, 255, 255, 255)) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg)
    paste_center(canvas, fit(mark, size, fill))
    return canvas


def build_icons(mark: Image.Image) -> list[str]:
    written = []

    # Regular icons: mark at 66% of the canvas.
    for name, size in (("icon-512.png", 512), ("icon-192.png", 192)):
        make_icon(size, mark, 0.66).convert("RGB").save(ASSETS / name, "PNG")
        written.append(name)

    # Maskable: Android crops to a circle of 80% width, so the artwork must
    # stay inside ~60% or a corner of the cap gets clipped.
    make_icon(512, mark, 0.58).convert("RGB").save(ASSETS / "icon-maskable-512.png", "PNG")
    written.append("icon-maskable-512.png")

    # iOS refuses transparency and rounds the corners itself.
    make_icon(180, mark, 0.70).convert("RGB").save(ASSETS / "apple-touch-icon.png", "PNG")
    written.append("apple-touch-icon.png")
    return written


def _text(draw: ImageDraw.ImageDraw, xy, s: str, f, fill, anchor="la", spacing=0):
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)


def build_og(mark: Image.Image) -> str:
    """1200x630 social card: dark brand field, logo tile, headline, chips."""
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), "#0f172a")
    d = ImageDraw.Draw(img, "RGBA")

    # Ambient glows — teal low-left, gold high-right, like the app chrome.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-320, 240, 520, 1000), fill=(14, 165, 164, 90))
    gd.ellipse((820, -360, 1560, 380), fill=(224, 165, 38, 66))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img, "RGBA")

    # Logo tile, top-left.
    tile = 132
    tx, ty = 78, 74
    d.rounded_rectangle((tx, ty, tx + tile, ty + tile), radius=34,
                        fill=(255, 255, 255, 255))
    paste_center_tile = fit(mark, tile, 0.74)
    img.alpha_composite(
        paste_center_tile,
        (tx + (tile - paste_center_tile.width) // 2,
         ty + (tile - paste_center_tile.height) // 2))
    d = ImageDraw.Draw(img, "RGBA")

    # Wordmark next to the tile.
    f_word = font(F_HEAD, 62)
    d.text((tx + tile + 30, ty + 30), "Learn", font=f_word, fill="#ffffff", anchor="lm")
    w_learn = d.textlength("Learn", font=f_word)
    d.text((tx + tile + 30 + w_learn, ty + 30), "ify", font=f_word,
           fill=BRAND_TEAL, anchor="lm")
    d.text((tx + tile + 31, ty + 74), "D I G I T A L   L E A R N I N G   P O R T A L",
           font=font(F_BODY, 20), fill="#94a3b8", anchor="lm")

    # Tagline chip — solid gold with dark text so it stays readable; a gold
    # wash with gold text was effectively invisible at feed-preview size.
    f_chip = font(F_BOLD, 26)
    chip_txt = "Check & Mate"
    cw = d.textlength(chip_txt, font=f_chip) + 46
    cx, cy = tx, ty + tile + 74
    d.rounded_rectangle((cx, cy, cx + cw, cy + 50), radius=25, fill=BRAND_GOLD)
    d.text((cx + 23, cy + 25), chip_txt, font=f_chip, fill="#0f172a", anchor="lm")

    # Headline.
    f_h1 = font(F_HEAD, 78)
    d.text((78, 400), "Build capacity,", font=f_h1, fill="#ffffff", anchor="lm")
    d.text((78, 484), "prove competency.", font=f_h1, fill=BRAND_TEAL, anchor="lm")

    # Right-hand rule list.
    f_li = font(F_BODY, 25)
    items = ["Courses & live sessions", "Practice sets and formal exams",
             "Certificates and Veda reports"]
    ly = 300
    for it in items:
        d.ellipse((742, ly - 9, 760, ly + 9), fill=BRAND_GOLD)
        d.text((780, ly), it, font=f_li, fill="#cbd5e1", anchor="lm")
        ly += 54

    # Footer rule + URL.
    d.line((78, 566, W - 78, 566), fill=(255, 255, 255, 26), width=2)
    d.text((78, 596), "learnify.hosteler.shop", font=font(F_BODY, 24),
           fill="#94a3b8", anchor="lm")
    d.text((W - 78, 596), "Digital Capacity Building & Learning Management Portal",
           font=font(F_BODY, 24), fill="#64748b", anchor="rm")

    out = ASSETS / "og-cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.name


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not LOGO.exists():
        print(f"missing source logo: {LOGO}", file=sys.stderr)
        return 1
    mark = logo_mark()
    print(f"logo mark {mark.size} (from {LOGO.name})")
    made = build_icons(mark)
    made.append(build_og(mark))
    for n in made:
        p = ASSETS / n
        print(f"  {n:26} {p.stat().st_size // 1024:>5} KB  {Image.open(p).size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
