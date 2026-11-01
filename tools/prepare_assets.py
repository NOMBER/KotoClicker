"""
Image preparation for KotoClick (running it is NOT required: the finished
files are already in assets/). Needs only Pillow.

What it does:
  1. Removes the near-white background: a flood fill from the image edges with a tolerance,
     so white highlights inside (eyes etc.) are left untouched.
  2. Softens the edge (a semi-transparent rim) so there is no white halo.
  3. Crops empty margins and saves a PNG.
  (The cat, its "hat" and the icon are prepared by tools/prepare_cat.py.)

Note about the shipped assets/mouse.png: it was additionally fixed by hand. The white gap
between the mouse's legs is enclosed by the drawing, so a flood fill from the edges cannot
reach it and it stayed white. To reproduce that fix, pass extra background seed points
(in source image pixels) with --seed X,Y (repeatable), one inside each enclosed white gap,
e.g. a point between the legs. Without --force the script does not overwrite an existing
assets/mouse.png and writes assets/mouse.new.png instead, so the hand-fixed file stays safe.

Run:  python tools/prepare_assets.py mouse.jpg [--seed X,Y ...] [--force]
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SENTINEL = (255, 0, 255)  # marker colour for the background (bright magenta, never used in the artwork)


def remove_background(src: Path, tolerance: int = 38, crop: bool = True, extra_seeds=()) -> Image.Image:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    work = img.copy()
    # Flood-fill the background from points all around the border (in case of background "islands")
    step = max(1, min(w, h) // 32)
    seeds = [(x, 0) for x in range(0, w, step)] + [(x, h - 1) for x in range(0, w, step)]
    seeds += [(0, y) for y in range(0, h, step)] + [(w - 1, y) for y in range(0, h, step)]
    # extra seeds (--seed X,Y) for white gaps enclosed by the drawing, e.g. between the mouse's legs
    seeds += [(x, y) for x, y in extra_seeds if 0 <= x < w and 0 <= y < h]
    for sx, sy in seeds:
        r, g, b = work.getpixel((sx, sy))
        if (r, g, b) != SENTINEL and min(r, g, b) > 200:
            ImageDraw.floodfill(work, (sx, sy), SENTINEL, thresh=tolerance)

    # Background mask: 255 where the pixel became the marker
    rr, gg, bb = work.split()
    m_r = rr.point(lambda v: 255 if v == 255 else 0)
    m_g = gg.point(lambda v: 255 if v == 0 else 0)
    m_b = bb.point(lambda v: 255 if v == 255 else 0)
    bg = ImageChops.multiply(ImageChops.multiply(m_r, m_g), m_b)

    # Base alpha: everything that is not background is opaque
    alpha = ImageChops.invert(bg)

    # A 2-pixel rim around the object: transparency from the pixel's "darkness",
    # so anti-aliased outline pixels (blended with white) become semi-transparent
    edge = ImageChops.subtract(bg.filter(ImageFilter.MaxFilter(5)), bg)  # rim outside the background
    edge = ImageChops.multiply(edge, alpha.filter(ImageFilter.MaxFilter(5)))
    gray = img.convert("L")
    soft = gray.point(lambda v: max(0, min(255, (255 - v) * 5)))
    alpha = Image.composite(ImageChops.lighter(soft, Image.new("L", img.size, 0)), alpha,
                            edge.point(lambda v: 255 if v else 0))
    alpha = Image.composite(Image.new("L", img.size, 0), alpha, bg)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))

    out = img.convert("RGBA")
    out.putalpha(alpha)
    bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox and crop:
        pad = 6
        bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(w, bbox[2] + pad), min(h, bbox[3] + pad))
        out = out.crop(bbox)
    return out


def fit(img: Image.Image, max_side: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    return img


def main():
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    seeds, files = [], []
    i = 0
    while i < len(args):
        if args[i] == "--seed" and i + 1 < len(args):
            x, y = args[i + 1].split(",")
            seeds.append((int(x), int(y)))
            i += 2
        else:
            files.append(args[i])
            i += 1
    if not files:
        print(__doc__)
        sys.exit(1)
    ASSETS.mkdir(parents=True, exist_ok=True)
    mouse = remove_background(Path(files[0]), extra_seeds=seeds)
    # never silently replace the hand-fixed assets/mouse.png
    target = ASSETS / "mouse.png"
    if target.exists() and not force:
        target = ASSETS / "mouse.new.png"
    fit(mouse, 520).save(target, optimize=True)
    print(f"Done: {target.name} (the cat and the icon: tools/prepare_cat.py)")


if __name__ == "__main__":
    main()
