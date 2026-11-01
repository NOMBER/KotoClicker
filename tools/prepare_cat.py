"""
Prepares the cat from two pictures (asleep / awake). Running it is NOT required:
the finished files are already in assets/. Needs Pillow, numpy and opencv-python
(developer only, the app itself does not need them).

What it does:
  1. Removes the white background from both pictures (like tools/prepare_assets.py)
     and crops them IDENTICALLY so the cat does not "jump" when the picture changes.
  2. Finds the violet headset (the "hat") on the head by colour and moves it
     to a separate layer cat_*_hat.png, which the window swings on every click.
  3. Paints ginger fur under the headset (inpaint) so no hole shows while it swings:
     that gives the cat_*_base.png layer.
  4. Writes the hat pivot point to cat_layers.json and makes the kotoclick.ico icon.

Run:  python tools/prepare_cat.py sleep.jpg awake.jpg
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_assets import ASSETS, fit, remove_background  # noqa: E402

# Head area in the 1024x1024 source picture (the button below is violet too: leave it alone)
HEAD_ROI = (90, 420, 260, 490)          # y0, y1, x0, x1
PIVOT = (470, 112)                      # where the headband touches the top of the head: we swing around this point
MAX_SIDE = 640


def headset_mask(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = (hsv[..., i].astype(int) for i in range(3))
    m = ((h >= 118) & (h <= 165) & (s >= 50) & (v >= 25)).astype(np.uint8) * 255
    roi = np.zeros_like(m)
    y0, y1, x0, x1 = HEAD_ROI
    roi[y0:y1, x0:x1] = 255
    m &= roi
    # only large pieces (no random violet dots)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 300:
            keep[lab == i] = 255
    return keep


def split(src: Path):
    rgba = np.array(remove_background(src, crop=False))
    rgb, alpha = rgba[..., :3].copy(), rgba[..., 3].copy()
    mask = headset_mask(rgb)
    ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    hat_m = cv2.dilate(mask, ell, iterations=1)                 # + dark outline and smoothing
    hole = cv2.dilate(mask, ell, iterations=3)                  # what gets painted over with fur

    # Hat layer: the source pixels with a soft edge
    soft = cv2.GaussianBlur(hat_m, (0, 0), 0.8).astype(np.float32) / 255.0
    hat = np.dstack([rgb, (alpha.astype(np.float32) * soft).astype(np.uint8)])

    # Base: paint fur under the hat, transparency outside the head
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    filled = cv2.cvtColor(cv2.inpaint(bgr, hole, 12, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
    a_fill = cv2.inpaint(alpha, hole, 12, cv2.INPAINT_TELEA)
    a_fill = np.where(a_fill > 140, 255, 0).astype(np.uint8)
    a_fill = cv2.GaussianBlur(a_fill, (0, 0), 0.8)
    base_rgb = np.where(hole[..., None] > 0, filled, rgb)
    base_a = np.where(hole > 0, a_fill, alpha)
    base = np.dstack([base_rgb, base_a])
    return rgba, base, hat


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    layers = {}
    for name, src in (("sleep", Path(sys.argv[1])), ("awake", Path(sys.argv[2]))):
        layers[name] = split(src)
    # a common crop box for both pictures
    boxes = [Image.fromarray(full[..., 3]).point(lambda v: 255 if v > 8 else 0).getbbox()
             for full, _, _ in layers.values()]
    pad = 6
    box = (min(b[0] for b in boxes) - pad, min(b[1] for b in boxes) - pad,
           max(b[2] for b in boxes) + pad, max(b[3] for b in boxes) + pad)
    bw, bh = box[2] - box[0], box[3] - box[1]
    for name, (full, base, hat) in layers.items():
        for suffix, arr in (("", full), ("_base", base), ("_hat", hat)):
            img = Image.fromarray(arr, "RGBA").crop(box)
            fit(img, MAX_SIDE).save(ASSETS / f"cat_{name}{suffix}.png", optimize=True)
    meta = {"pivot": [(PIVOT[0] - box[0]) / bw, (PIVOT[1] - box[1]) / bh],
            "note": "pivot: fraction of the image width/height the hat swings around"}
    (ASSETS / "cat_layers.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Icon: the awake cat's head
    cat = Image.fromarray(layers["awake"][0], "RGBA").crop(box)
    cw, ch = cat.size
    side = int(cw * 0.74)
    left = int(cw * 0.53 - side / 2)
    head = cat.crop((left, 0, left + side, side))
    icon = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    icon.alpha_composite(head)
    icon.save(ASSETS / "kotoclick.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    fit(icon, 256).save(ASSETS / "icon.png", optimize=True)
    print("Done:", meta)


if __name__ == "__main__":
    main()
