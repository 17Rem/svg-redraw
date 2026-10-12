# -*- coding: utf-8 -*-
"""Look at the reference before tracing it: report size / palette / subject extent and
write gridded zoom crops so the parts that need hand-drawn overlays (eyes, mouth, props)
can be measured off real coordinates instead of guessed.

Usage:
  python analyze.py --src "ref.jpg" --out build/crops [--scale 1.6] \
      [--crop head:330,30,700,400 ...] [--zoom eye:490,200,580,270:6]
"""
import argparse, os

import numpy as np
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--scale", type=float, default=1.6)
ap.add_argument("--crop", action="append", default=[], help="name:x0,y0,x1,y1 (repeatable)")
ap.add_argument("--zoom", action="append", default=[],
                help="name:x0,y0,x1,y1:scale with a fine measurement grid (repeatable)")
ap.add_argument("--k", type=int, default=20, help="palette clusters to report")
args = ap.parse_args()

im = Image.open(args.src).convert("RGB")
W, H = im.size
arr = np.asarray(im).astype(np.float32)
os.makedirs(args.out, exist_ok=True)
print("size %d x %d" % (W, H))

dist_white = np.sqrt(((arr - 255.0) ** 2).sum(axis=2))
for thr in (26.0, 46.0, 90.0):
    ys, xs = np.nonzero(dist_white > thr)
    if len(ys):
        print("  pixels farther than %5.1f from white: %6.2f%%  bbox x%d-%d y%d-%d"
              % (thr, 100.0 * len(ys) / (W * H), xs.min(), xs.max(), ys.min(), ys.max()))

ys, xs = np.nonzero(dist_white > 20)
pix = arr[ys, xs]
rng = np.random.default_rng(3)
s = pix[rng.choice(len(pix), size=min(150000, len(pix)), replace=False)]
K = args.k
cent = np.empty((K, 3), np.float32); cent[0] = s[rng.integers(len(s))]
d2 = ((s - cent[0]) ** 2).sum(1)
for i in range(1, K):
    p = d2 / max(d2.sum(), 1e-9); cent[i] = s[rng.choice(len(s), p=p)]
    d2 = np.minimum(d2, ((s - cent[i]) ** 2).sum(1))
for _ in range(16):
    lab = ((s[:, None, :] - cent[None, :, :]) ** 2).sum(2).argmin(1)
    for i in range(K):
        m = lab == i
        if m.sum():
            cent[i] = s[m].mean(0)
cnt = np.bincount(lab, minlength=K)
print("palette:")
for i in np.argsort(-cnt):
    c = cent[i]
    print("   #%02x%02x%02x  %6.2f%%" % (int(c[0]), int(c[1]), int(c[2]), 100.0 * cnt[i] / len(s)))


def grid(img, ox, oy, step, big):
    d = ImageDraw.Draw(img)
    w, h = img.size
    for x in range(0, w, step):
        gx = ox + x
        major = gx % big == 0
        d.line([(x, 0), (x, h)], fill=(255, 0, 0) if major else (255, 175, 175),
               width=2 if major else 1)
        if major:
            d.text((x + 3, 3), str(gx), fill=(190, 0, 0))
    for y in range(0, h, step):
        gy = oy + y
        major = gy % big == 0
        d.line([(0, y), (w, y)], fill=(0, 90, 255) if major else (170, 200, 255),
               width=2 if major else 1)
        if major:
            d.text((3, y + 3), str(gy), fill=(0, 60, 200))
    return img


for spec in args.crop:
    name, _, box = spec.partition(":")
    x0, y0, x1, y1 = (int(v) for v in box.split(","))
    c = im.crop((x0, y0, x1, y1))
    if args.scale != 1.0:
        c = c.resize((int(c.width * args.scale), int(c.height * args.scale)), Image.LANCZOS)
    c = grid(c, x0, y0, int(round(50 * args.scale)), int(round(100 * args.scale)))
    c.save(os.path.join(args.out, name + ".png"))
    print("crop", name, (x0, y0, x1, y1), c.size)

for spec in args.zoom:
    name, _, rest = spec.partition(":")
    box, _, sc = rest.rpartition(":")
    s = float(sc)
    x0, y0, x1, y1 = (int(v) for v in box.split(","))
    c = im.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
    c = grid(c, x0, y0, int(round(10 * s)), int(round(50 * s)))
    c.save(os.path.join(args.out, name + ".png"))
    print("zoom", name, (x0, y0, x1, y1), "x%.0f" % s, c.size)
