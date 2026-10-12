# -*- coding: utf-8 -*-
"""Vectorise a reference illustration into a lineart layer + flat colour layer.

Pipeline (mirrors how the illustration was actually painted):
  1. lineart  - black-hat response of the greyscale image picks out every ink stroke; wide
                dark masses (large dark garments) are rejected and stay in the colour layer
  2. inpaint  - the ink band is diffused away so the colour layer is clean flat pigment
  3. palette  - k-means over the inpainted canvas; ink pixels inherit the nearest label
  4. regions  - exact pixel boundary walk, adaptive simplification, grow=0

Usage:
  python trace.py --src "ref.jpg" --out build --tag a \
      [--k 72] [--minpx 6] [--eps 0.55] [--speck 14] [--colthr 22] \
      [--line-thr 17] [--dark 60] [--maxw 6]

Writes <out>/trace_<tag>.json  = {"w","h","regions":[...], "strokes":[...]}
and   <out>/mask_ink_<tag>.png for eyeballing the extracted lineart.
"""
import argparse, json, os, sys, time

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, fast  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True, help="reference image (jpg/png)")
ap.add_argument("--out", required=True, help="output directory for trace_<tag>.json")
ap.add_argument("--tag", default="a", help="suffix for output files")
ap.add_argument("--k", type=int, default=64, help="k-means palette size (48-80 typical)")
ap.add_argument("--minpx", type=int, default=6, help="smallest traced patch, px")
ap.add_argument("--eps", type=float, default=0.55, help="RDP tolerance for large patches")
ap.add_argument("--speck", type=int, default=14, help="speck merge size limit")
ap.add_argument("--colthr", type=float, default=22.0,
                help="only absorb a speck when its colour is this close to the neighbour")
ap.add_argument("--line-thr", type=float, default=12.0, dest="line_thr",
                help="black-hat threshold for ink strokes")
ap.add_argument("--dark", type=float, default=30.0,
                help="how much darker than the local blur counts as ink")
ap.add_argument("--maxw", type=float, default=7.0,
                help="reject ink components wider than this (they are masses, not strokes)")
ap.add_argument("--soft-lum", type=float, default=175.0, dest="soft_lum",
                help="components lighter than this are blurred strands -> thinned by 1px")
ap.add_argument("--char-thr", type=float, default=100.0, dest="char_thr",
                help="distance-from-white that marks definite character pixels")
ap.add_argument("--max-mass", type=int, default=22000, dest="max_mass",
                help="reject ink components larger than this (big flat dark masses)")
args = ap.parse_args()

SRC = args.src
OUT = args.out
os.makedirs(OUT, exist_ok=True)
t0 = time.time()

K = args.k
MINPX = args.minpx
EPS = args.eps
SPECK = args.speck
COLTHR = args.colthr
LINE_THR = args.line_thr
DARK = args.dark
MAXW = args.maxw
SOFT_LUM = args.soft_lum
CHAR_THR = args.char_thr
MAX_MASS = args.max_mass
TAG = args.tag


def log(*a):
    print(*a, "%.1fs" % (time.time() - t0), flush=True)



img = Image.open(SRC).convert("RGB").filter(ImageFilter.MedianFilter(3))
raw = np.asarray(img).astype(np.float32)
H, W = raw.shape[:2]
log("size", W, H)
grey = 0.299 * raw[:, :, 0] + 0.587 * raw[:, :, 1] + 0.114 * raw[:, :, 2]
dist_white = np.sqrt(((raw - 255.0) ** 2).sum(axis=2))


def flood(seed):
    m = np.zeros((H, W), bool); st = []
    for x in range(W):
        for y in (0, H - 1):
            if seed[y, x] and not m[y, x]:
                m[y, x] = True; st.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if seed[y, x] and not m[y, x]:
                m[y, x] = True; st.append((y, x))
    while st:
        y, x = st.pop()
        if y + 1 < H and seed[y + 1, x] and not m[y + 1, x]:
            m[y + 1, x] = True; st.append((y + 1, x))
        if y and seed[y - 1, x] and not m[y - 1, x]:
            m[y - 1, x] = True; st.append((y - 1, x))
        if x + 1 < W and seed[y, x + 1] and not m[y, x + 1]:
            m[y, x + 1] = True; st.append((y, x + 1))
        if x and seed[y, x - 1] and not m[y, x - 1]:
            m[y, x - 1] = True; st.append((y, x - 1))
    return m


plate = flood(dist_white < 24.0)
strong = dist_white > CHAR_THR
big = geo.dilate(strong, 9)
comps = geo.components(big, minpx=200)
comps.sort(key=len, reverse=True)
core = np.zeros((H, W), bool)
core[comps[0][:, 0], comps[0][:, 1]] = True
char = geo.erode(~flood(~core), 9)
log("char %.1f%%" % (100.0 * char.mean()))


# ---------------------------------------------------------------- 1. lineart
R = 2
closing = geo.gray_erode(geo.gray_dilate(grey, R), R)
blackhat = closing - grey
g8 = np.clip(grey, 0, 255).astype(np.uint8)
blur = np.asarray(Image.fromarray(g8).filter(ImageFilter.BoxBlur(9))).astype(np.float32)
cand = (blackhat > LINE_THR) | (grey < blur - DARK)
cand &= dist_white > 14.0
log("ink candidates", int(cand.sum()))

ink = np.zeros((H, W), bool)
kept = dropped = thinned = 0
for c in geo.components(cand, minpx=6):
    area = len(c)
    yy0, xx0 = c.min(0); yy1, xx1 = c.max(0)
    maskc = np.zeros((H, W), bool); maskc[c[:, 0], c[:, 1]] = True
    inner = geo.erode(maskc, 1)
    per = float((maskc & ~inner).sum()) + 1.0
    width = 2.0 * area / per
    if width > MAXW or area > MAX_MASS:
        dropped += 1
        continue
    # soft (light) strokes are the blurred under-drawing strands: keep them but a hair
    # thinner so they read as hair over the face instead of as ink
    mlum = float(np.mean(grey[c[:, 0], c[:, 1]]))
    if mlum > SOFT_LUM and inner.sum() >= area * 0.55:
        maskc = inner
        thinned += 1
    ink |= maskc
    kept += 1
log("ink components", kept, "thinned", thinned, "dropped", dropped,
    "ink px", int(ink.sum()), "%.2f%%" % (100.0 * ink.mean()))
Image.fromarray((ink * 255).astype(np.uint8)).save(OUT + r"\mask_ink_%s.png" % TAG)

ink_band = geo.dilate(ink, 2)

# ---------------------------------------------------------------- 2. inpaint
work = raw.copy()
valid = ~ink_band
work[~valid] = 0.0
todo = ~valid
for it in range(24):
    if not todo.any():
        break
    acc = np.zeros_like(work); cnt = np.zeros((H, W), np.float32)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
        s = np.roll(np.roll(work, dy, 0), dx, 1)
        v = np.roll(np.roll(valid, dy, 0), dx, 1).astype(np.float32)
        acc += s * v[:, :, None]; cnt += v
    add = todo & (cnt > 0)
    work[add] = acc[add] / cnt[add][:, None]
    valid |= add; todo &= ~add
log("inpaint")
work = geo.bilateral(work, 1, 1.0, 55.0)
log("bilateral")

# ---------------------------------------------------------------- 3. palette
sel = ~ink_band
ys, xs = np.nonzero(sel)
pix = work[ys, xs]
rng = np.random.default_rng(11)
sidx = rng.choice(len(pix), size=min(340000, len(pix)), replace=False)
sample = pix[sidx]
cent = np.empty((K, 3), np.float32)
cent[0] = sample[rng.integers(len(sample))]
d2 = ((sample - cent[0]) ** 2).sum(1)
for i in range(1, K):
    p = d2 / max(d2.sum(), 1e-9)
    cent[i] = sample[rng.choice(len(sample), p=p)]
    d2 = np.minimum(d2, ((sample - cent[i]) ** 2).sum(1))
for it in range(20):
    d = ((sample[:, None, :] - cent[None, :, :]) ** 2).sum(2)
    lab = d.argmin(1)
    for i in range(K):
        m = lab == i
        if m.sum():
            cent[i] = sample[m].mean(0)
log("kmeans")

labels = np.full((H, W), -1, np.int32)
flat = work.reshape(-1, 3)
o = np.empty(len(flat), np.int32)
CH = 120000
for i in range(0, len(flat), CH):
    seg = flat[i:i + CH]
    dd = ((seg[:, None, :] - cent[None, :, :]) ** 2).sum(2)
    o[i:i + CH] = dd.argmin(1)
labels = o.reshape(H, W)
# ink pixels inherit the nearest colour label so the flats continue underneath the strokes
res = labels.copy()
todo = ink_band & (labels < 0)
for _ in range(10):
    if not todo.any():
        break
    acc = np.zeros((H, W), np.int64); cnt = np.zeros((H, W), np.int32)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
        l = np.roll(np.roll(res, dy, 0), dx, 1)
        v = (l >= 0).astype(np.int32)
        acc += l * v; cnt += v
    add = todo & (cnt > 0)
    res[add] = (acc[add] // cnt[add]).astype(np.int32)
    todo &= ~add
labels = res
log("labels")

# ---------------------------------------------------------------- 3b. colour aware speck removal
CD = np.sqrt(((cent[:, None, :] - cent[None, :, :]) ** 2).sum(2))


def speck_pass():
    moved = 0
    for lb in range(K):
        m = labels == lb
        if not m.any():
            continue
        for c in geo.components(m, minpx=1):
            if len(c) >= SPECK:
                continue
            cy0, cx0 = c.min(0); cy1, cx1 = c.max(0)
            pad = 3
            Y0 = max(0, cy0 - pad); Y1 = min(H, cy1 + pad + 1)
            X0 = max(0, cx0 - pad); X1 = min(W, cx1 + pad + 1)
            win = labels[Y0:Y1, X0:X1]
            loc = np.zeros(win.shape, bool)
            loc[c[:, 0] - Y0, c[:, 1] - X0] = True
            nb = win[geo.dilate(loc, 2) & ~loc]
            nb = nb[(nb >= 0) & (nb != lb)]
            if nb.size == 0:
                continue
            vals, counts = np.unique(nb, return_counts=True)
            pick = -1
            for k in np.argsort(-counts)[:4]:
                if CD[lb, int(vals[k])] < COLTHR:
                    pick = int(vals[k]); break
            if pick < 0:
                continue
            labels[c[:, 0], c[:, 1]] = pick
            moved += 1
    return moved


for rnd in range(3):
    mv = speck_pass()
    log("speck", rnd, mv)
    if mv == 0:
        break


def final_fill():
    """No pixel may stay uncovered: every leftover patch below MINPX is absorbed."""
    moved = 0
    for lb in range(K):
        m = labels == lb
        if not m.any():
            continue
        for c in geo.components(m, minpx=1):
            if len(c) >= MINPX:
                continue
            cy0, cx0 = c.min(0); cy1, cx1 = c.max(0)
            pad = 3
            Y0 = max(0, cy0 - pad); Y1 = min(H, cy1 + pad + 1)
            X0 = max(0, cx0 - pad); X1 = min(W, cx1 + pad + 1)
            win = labels[Y0:Y1, X0:X1]
            loc = np.zeros(win.shape, bool)
            loc[c[:, 0] - Y0, c[:, 1] - X0] = True
            nb = win[geo.dilate(loc, 3) & ~loc]
            nb = nb[nb != lb]
            if nb.size == 0:
                continue
            vals, counts = np.unique(nb, return_counts=True)
            labels[c[:, 0], c[:, 1]] = int(vals[counts.argmax()])
            moved += 1
    return moved


for rnd in range(4):
    mv = final_fill()
    log("finalfill", rnd, mv)
    if mv == 0:
        break

# ---------------------------------------------------------------- 4. regions
lum = 0.299 * work[:, :, 0] + 0.587 * work[:, :, 1] + 0.114 * work[:, :, 2]
lum8 = np.clip(lum, 0, 255).astype(np.uint8)
local_hi = np.asarray(Image.fromarray(lum8).filter(ImageFilter.MaxFilter(7))).astype(np.float32)
local_lo = np.asarray(Image.fromarray(lum8).filter(ImageFilter.MinFilter(7))).astype(np.float32)
# local base tone: the median over a wide window is what the eye reads as "the colour of
# this area", so a patch is only a shadow / highlight relative to that base
local_med = np.asarray(Image.fromarray(lum8).filter(ImageFilter.MedianFilter(21))).astype(np.float32)
log("local median")

regions = []
for lb in range(K):
    m = labels == lb
    if not m.any():
        continue
    for c in geo.components(m, minpx=MINPX):
        area = len(c)
        yy0, xx0 = c.min(0); yy1, xx1 = c.max(0)
        maskc = np.zeros((H, W), bool); maskc[c[:, 0], c[:, 1]] = True
        inner = geo.erode(maskc, 1)
        sel2 = inner if inner.sum() > max(6, area * 0.3) else maskc
        col = np.median(raw[sel2], axis=0)
        eps = 0.25 if area < 30 else (0.32 if area < 400 else 0.45)
        sm = 0 if width <= 3.5 else (1 if area < 400 else 2)
        d = fast.path_local(maskc, eps=eps, grow=0, smooth=sm, linear=True)
        if not d:
            continue
        bnd = maskc & ~inner
        width = 2.0 * area / (float(bnd.sum()) + 1.0)
        lv = float(0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2])
        pad = 5
        patch_hi = local_hi[max(0, yy0 - pad):yy1 + pad + 1, max(0, xx0 - pad):xx1 + pad + 1]
        patch_lo = local_lo[max(0, yy0 - pad):yy1 + pad + 1, max(0, xx0 - pad):xx1 + pad + 1]
        hi = float(np.percentile(patch_hi, 92)); lo = float(np.percentile(patch_lo, 8))
        rel = (lv - lo) / max(hi - lo, 26.0)
        med = local_med[max(0, yy0 - pad):yy1 + pad + 1, max(0, xx0 - pad):xx1 + pad + 1]
        base_lum = float(np.median(med))
        ratio = lv / max(base_lum, 12.0)
        if width <= 3.2 and rel < 0.40:
            kind = "line"
        elif ratio < 0.74:
            kind = "deep"
        elif ratio < 0.90:
            kind = "shadow"
        elif ratio > 1.15:
            kind = "light"
        else:
            kind = "base"
        fx0, fx1 = max(0, xx0 - 3), min(W, xx1 + 4)
        fy0, fy1 = max(0, yy0 - 3), min(H, yy1 + 4)
        sub = char[fy0:fy1, fx0:fx1]
        cov = float(sub.sum()) / max(1.0, float(sub.size))
        zone = "char" if cov > 0.55 else ("bg" if cov < 0.15 else "edge")
        regions.append({
            "hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in col),
            "lum": round(lv, 1), "rel": round(rel, 3), "ratio": round(ratio, 3),
            "w": round(width, 2), "area": int(area), "kind": kind, "zone": zone,
            "bbox": [int(xx0), int(yy0), int(xx1), int(yy1)],
            "cx": round(float(c[:, 1].mean()), 1), "cy": round(float(c[:, 0].mean()), 1),
            "d": d,
        })
log("fill regions", len(regions))

# ---------------------------------------------------------------- ink layer
strokes = []
for c in geo.components(ink, minpx=5):
    area = len(c)
    maskc = np.zeros((H, W), bool); maskc[c[:, 0], c[:, 1]] = True
    col = np.mean(raw[c[:, 0], c[:, 1]], axis=0)
    eps = 0.24 if area < 300 else 0.30
    d = fast.path_local(maskc, eps=eps, grow=0, smooth=0, linear=True)
    if not d:
        continue
    strokes.append({
        "hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in col),
        "area": int(area),
        "bbox": [int(c[:, 1].min()), int(c[:, 0].min()), int(c[:, 1].max()), int(c[:, 0].max())],
        "cx": round(float(c[:, 1].mean()), 1), "cy": round(float(c[:, 0].mean()), 1),
        "d": d,
    })
log("ink strokes", len(strokes))
from collections import Counter
print(Counter(r["kind"] for r in regions))
json.dump({"w": W, "h": H, "regions": regions, "strokes": strokes},
          open(OUT + r"\trace_%s.json" % TAG, "w", encoding="utf-8"))
log("saved %.1f KB" % (os.path.getsize(OUT + r"\trace_%s.json" % TAG) / 1024.0))
