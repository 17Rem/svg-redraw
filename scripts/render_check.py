# -*- coding: utf-8 -*-
"""Gate the result: render the emitted artwork 1:1 in headless Chrome and diff it against
the reference image, plus zoomed side-by-side crops for eyeballing.

Usage:
  python render_check.py --svg build/art_a.svg --ref "ref.jpg" --out build \
      [--chrome <browser binary>] [--crops "380,180,600,340;380,1500,620,1700"]

Prints `mean|d|` (0-255) and the share of pixels off by more than 25. For a dense anime
illustration a good trace lands around 6-8 mean / 7-9 % > 25; the same palette rasterised
directly sits near 2-3, so a much higher number means the *vectorising* step is losing
detail, not that the palette is wrong (see references/tuning.md).
"""
import argparse, os, shutil, subprocess, sys

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--svg", required=True)
ap.add_argument("--ref", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--tag", default="check")
ap.add_argument("--chrome", default="", help="browser binary; auto-detected when omitted")
ap.add_argument("--crops", default="", help="semicolon separated x0,y0,x1,y1 boxes")
args = ap.parse_args()

CHROME_CANDIDATES = [
    args.chrome,
    os.environ.get("CHROME_HEADLESS", ""),
    shutil.which("chrome-headless-shell") or "",
    shutil.which("chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("google-chrome") or "",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
CHROME = next((c for c in CHROME_CANDIDATES if c and os.path.exists(c)), None)
if not CHROME:
    sys.exit("no Chrome/Chromium found - pass --chrome <path> or set CHROME_HEADLESS.\n"
             "Remotion ships one under <remotion>/node_modules/.remotion/"
             "chrome-headless-shell/<platform>/")

os.makedirs(args.out, exist_ok=True)
ref = Image.open(args.ref).convert("RGB")
W, H = ref.size

svg = open(args.svg, encoding="utf-8").read()
page = os.path.join(args.out, "flat_%s.html" % args.tag)
open(page, "w", encoding="utf-8").write(
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'html,body{margin:0;padding:0;overflow:hidden;background:#fff}'
    'svg{display:block;width:%dpx;height:%dpx}#layer-sketch{display:none}'
    '</style></head><body>%s</body></html>' % (W, H, svg))
png = os.path.join(args.out, "flat_%s.png" % args.tag)
subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=1", "--window-size=%d,%d" % (W, H),
                "--virtual-time-budget=4000", "--screenshot=" + png,
                "file:///" + page.replace("\\", "/")], capture_output=True)
img = Image.open(png).convert("RGB")
a = np.asarray(img).astype(np.float32)
b = np.asarray(ref).astype(np.float32)
d = np.abs(a - b)
print("mean|d| %.2f   px>25 %.2f%%" % (d.mean(), 100.0 * (d.max(2) > 25).mean()))

w2 = 470
h2 = int(round(w2 * H / W))
side = Image.new("RGB", (w2 * 2 + 10, h2), "white")
side.paste(ref.resize((w2, h2), Image.LANCZOS), (0, 0))
side.paste(img.resize((w2, h2), Image.LANCZOS), (w2 + 10, 0))
side.save(os.path.join(args.out, "side_%s.png" % args.tag))

boxes = [c for c in args.crops.split(";") if c.strip()]
for box in boxes:
    x0, y0, x1, y1 = (int(v) for v in box.split(","))
    aa = ref.crop((x0, y0, x1, y1)); bb = img.crop((x0, y0, x1, y1))
    cw, ch = aa.size
    canvas = Image.new("RGB", (cw * 2 + 8, ch), "white")
    canvas.paste(aa, (0, 0)); canvas.paste(bb, (cw + 8, 0))
    canvas.save(os.path.join(args.out, "cmp_%s_%d_%d.png" % (args.tag, x0, y0)))
print("wrote side_%s.png + %d crops into %s" % (args.tag, len(boxes), args.out))
