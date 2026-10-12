# -*- coding: utf-8 -*-
"""Build the layered SVG artwork + the self-contained HTML deliverables.

Turns trace_<tag>.json into:
  * <out>/art_<tag>.svg           the raw layered artwork fragment
  * <html-out>/<name>.html        static page, one complete self-contained file
  * <html-out>/<name>-demo.html   drawing-process player (same SVG + timeline JS)
  * <out>/<Name>Art.ts            the same SVG as a TS module for the Remotion video

Usage:
  python emit.py --trace build/trace_a.json --out build --html-out . \
      --name my-art --title "MY ART" --subtitle "纯 SVG 重绘 · 绘制流程回放" \
      --duration 88 [--overlay scripts/overlay_example.py] \
      [--ref-image "ref.jpg"] [--plate "#f9f5f8"] [--stroke 1.2]
"""
import argparse, importlib.util, json, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--trace", required=True)
ap.add_argument("--out", required=True, help="where art_<tag>.svg + the TS module go")
ap.add_argument("--html-out", default=".", help="where the two .html deliverables go")
ap.add_argument("--name", default="artwork", help="kebab-case deliverable base name")
ap.add_argument("--title", default="SVG REDRAW")
ap.add_argument("--subtitle", default="纯 SVG 重绘 · 绘制流程回放")
ap.add_argument("--duration", type=float, default=88.0, help="seconds of the drawing timeline")
ap.add_argument("--overlay", default="", help="python file exposing SKETCH_SVG / FACE_SVG")
ap.add_argument("--ref-image", default="", help="file name (next to the html) used by 对比原图")
ap.add_argument("--plate", default="#f9f5f8", help="paper colour behind the traced fills")
ap.add_argument("--stroke", default="1.2", help="same-colour stroke that seals hairline seams")
ap.add_argument("--tag", default="a")
args = ap.parse_args()

OUT = args.out
HTML_OUT = args.html_out
os.makedirs(OUT, exist_ok=True)
os.makedirs(HTML_OUT, exist_ok=True)
TAG = args.tag
DUR = args.duration
SW = args.stroke
NAME = args.name
TITLE = args.title
SUB = args.subtitle
REF_IMAGE = args.ref_image

overlay = None
if args.overlay:
    spec = importlib.util.spec_from_file_location("overlay", args.overlay)
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
OVERLAY = overlay is not None and hasattr(overlay, "SKETCH_SVG")
FACE_ON = overlay is not None and hasattr(overlay, "FACE_SVG")

t = json.load(open(args.trace, encoding="utf-8"))
W, H = t["w"], t["h"]
regions = t["regions"]
strokes = t.get("strokes", [])
print("fill regions", len(regions), "ink strokes", len(strokes))

PLATE = args.plate
KIND_ORDER = {"base": 0, "shadow": 1, "deep": 2, "light": 3, "line": 4}
KIND_CN = {"base": "固有色", "shadow": "一级阴影", "deep": "二级暗部",
           "light": "高光", "line": "细线"}


# ------------------------------------------------------------------ zones
def is_fx(r):
    x0, y0, x1, y1 = r["bbox"]
    return x0 >= 545 and y0 >= 205 and y1 <= 345


bg_regions, fx_regions, char_regions, char_strokes, fx_strokes = [], [], [], [], []
for r in regions:
    if is_fx(r):
        fx_regions.append(r)
    elif r.get("zone") == "bg":
        bg_regions.append(r)
    else:
        char_regions.append(r)
for s in strokes:
    (fx_strokes if is_fx(s) else char_strokes).append(s)

bg_regions.sort(key=lambda r: -r["area"])
char_regions.sort(key=lambda r: (KIND_ORDER.get(r["kind"], 9), -r["area"]))
fx_regions.sort(key=lambda r: -r["area"])
char_strokes.sort(key=lambda r: -r["area"])
fx_strokes.sort(key=lambda r: -r["area"])

# ------------------------------------------------------------------ timing
STAGES = [
    ("sketch", "构图 · 起草", 0.075),
    ("bg", "背景 · 铺底", 0.085),
    ("base", "固有色 · 铺色", 0.200),
    ("shadow", "一级阴影 · 体积", 0.085),
    ("deep", "二级暗部 · 压深", 0.065),
    ("light", "高光 · 提亮", 0.105),
    ("line", "细线 · 收形", 0.075),
    ("ink", "勾线 · 墨线", 0.200),
    ("face", "面部 · 刻画", 0.070),
    ("fx", "光效 · 彩虹棱镜", 0.060),
]
tot = sum(s[2] for s in STAGES)
T, acc = {}, 0.0
for k, lab, w in STAGES:
    T[k] = (acc / tot * DUR, (acc + w) / tot * DUR)
    acc += w
REVEAL = 0.32


def times_for(items):
    order = sorted(range(len(items)), key=lambda i: (items[i]["cy"], items[i]["cx"]))
    n = max(1, len(items))
    out = [0.0] * len(items)
    for rank, i in enumerate(order):
        out[i] = (rank / n) ** 0.88
    return out


def layer(gid, label, items, stage, cls, stroke=True):
    a, b = T[stage]
    span = max(0.001, b - a)
    fr = times_for(items)
    rows = ['<g id="layer-%s" class="art-layer" data-layer="%s" data-label="%s">'
            % (gid, stage, label)]
    for r, f in zip(items, fr):
        t0 = a + f * (span - REVEAL)
        # hairline seams between neighbours are closed with a same colour stroke; razor
        # thin patches are left unstroked so they keep their exact width
        st = (' stroke="%s" stroke-width="%s"' % (r["hex"], SW)
              if stroke and r.get("w", 9) > 3.5 else "")
        rows.append('<path class="rg %s" data-t="%.2f" data-d="%.2f" fill="%s"%s d="%s"/>'
                    % (cls, t0, REVEAL, r["hex"], st, r["d"]))
    rows.append("</g>")
    return "\n".join(rows)


def timed(fragment, stage, steps=None):
    """Give a hand authored fragment the same data-t/data-d reveal contract as the traced paths."""
    a, b = T[stage]
    span = max(0.001, b - a)
    head, sep, rest = fragment.partition(">")
    if not sep:
        return fragment
    n = steps or 14
    idx = [0]

    def repl(m):
        i = idx[0]; idx[0] += 1
        t0 = a + (min(i, n) / float(n)) * (span - REVEAL)
        tag = m.group(0)
        attr = ' data-t="%.2f" data-d="%.2f"' % (t0, REVEAL)
        # self closing tags must stay self closing, otherwise the following siblings
        # would be parsed as their children and silently disappear
        if tag.endswith("/>"):
            return tag[:-2] + attr + "/>"
        return tag[:-1] + attr + ">"

    inner = re.sub(r'<(path|ellipse|circle|rect|line|polygon|polyline|g)\b[^>]*?>', repl, rest)
    return head + sep + inner


body = []
body.append('<g id="layer-paper" class="art-layer" data-layer="paper" data-label="画纸">'
            '<rect id="paper-plate" width="%d" height="%d" fill="%s"/>'
            '<rect id="paper-wash" width="%d" height="%d" fill="url(#grad-paper)"/></g>'
            % (W, H, PLATE, W, H))
if OVERLAY:
    body.append(timed(overlay.SKETCH_SVG, "sketch", 22))
body.append(layer("bg", "背景 · 装饰", bg_regions, "bg", "z-bg"))
for kind in ("base", "shadow", "deep", "light", "line"):
    items = [r for r in char_regions if r["kind"] == kind]
    if items:
        body.append(layer(kind, KIND_CN[kind], items, kind, "z-" + kind))
body.append(layer("ink", "勾线 · 墨线", char_strokes, "ink", "z-ink", stroke=False))
if FACE_ON:
    body.append(timed(overlay.FACE_SVG, "face", 12))
body.append(layer("fx", "光效", fx_regions + fx_strokes, "fx", "z-fx"))
body.append('<rect id="paper-grain" width="%d" height="%d" fill="#ffffff" '
            'opacity="0.03" filter="url(#paper-grain-f)"/>' % (W, H))
ARTWORK = "\n".join(x for x in body if x)

STAGE_JSON = json.dumps([{"key": k, "label": lab, "from": round(T[k][0], 3),
                          "to": round(T[k][1], 3)} for k, lab, w in STAGES],
                        ensure_ascii=False)

DEFS = '''<defs>
    <linearGradient id="grad-paper" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="#fcfafc"/><stop offset="0.55" stop-color="#f9f5f9"/>
      <stop offset="1" stop-color="#f4eff6"/>
    </linearGradient>
    <radialGradient id="grad-iris" cx="0.44" cy="0.28" r="0.82">
      <stop offset="0" stop-color="#8f8ac0"/><stop offset="0.4" stop-color="#7974aa"/>
      <stop offset="0.76" stop-color="#615c94"/><stop offset="1" stop-color="#4b4677"/>
    </radialGradient>
    <linearGradient id="grad-iris-lower" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="1" stop-color="#d8d5ee" stop-opacity="0.72"/>
    </linearGradient>
    <radialGradient id="grad-blush" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#f0a9ad" stop-opacity="0.5"/>
      <stop offset="0.6" stop-color="#f0a9ad" stop-opacity="0.24"/>
      <stop offset="1" stop-color="#f0a9ad" stop-opacity="0"/>
    </radialGradient>
    <filter id="paper-grain-f" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" result="n"/>
      <feColorMatrix in="n" type="saturate" values="0"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.06"/></feComponentTransfer>
    </filter>
  </defs>'''

SVG = ('<svg id="redraw-art" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
       'preserveAspectRatio="xMidYMid meet" role="img" '
       'aria-labelledby="art-title art-desc">\n'
       '  <title id="art-title">%s（纯 SVG 重绘）</title>\n'
       '  <desc id="art-desc">以原生 SVG 路径分层绘制的插画：画纸、构图辅助线、背景、'
       '固有色、一级阴影、二级暗部、高光、细线、墨线勾线、面部刻画与光效。</desc>\n'
       '  %s\n%s\n</svg>' % (W, H, TITLE, DEFS, ARTWORK))

STATIC = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · 纯 SVG 重绘</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:radial-gradient(120% 80% at 50% -10%,#fdfbff 0%,#f0ecf7 42%,#ddd6ea 100%);
       display:flex;align-items:center;justify-content:center;padding:24px 14px;
       font-family:"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif}
  .artwork{margin:0;width:min(92vmin,780px);max-height:100%;aspect-ratio:__W__/__H__;
           filter:drop-shadow(0 26px 60px rgba(64,56,98,.26))}
  .artwork svg{display:block;width:100%;height:100%;border-radius:6px}
  #layer-sketch{display:none}
</style>
</head>
<body>
<figure class="artwork">
__SVG__
</figure>
</body>
</html>
'''

DEMO = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "demo_template.html"), encoding="utf-8").read()

HTML_NAME = os.path.join(HTML_OUT, NAME + ".html")
DEMO_NAME = os.path.join(HTML_OUT, NAME + "-demo.html")
TS_NAME = os.path.join(OUT, NAME.replace("-", "_") + "_art.ts")
TS_EXPORT = re.sub(r"[^A-Za-z0-9]+", "_", NAME).strip("_").upper()

open(os.path.join(OUT, "art_%s.svg" % TAG), "w", encoding="utf-8").write(SVG)
open(HTML_NAME, "w", encoding="utf-8").write(
    STATIC.replace("__SVG__", SVG).replace("__TITLE__", TITLE)
          .replace("__W__", str(W)).replace("__H__", str(H)))
open(DEMO_NAME, "w", encoding="utf-8").write(
    DEMO.replace("__SVG__", SVG)
        .replace("__DUR__", "%.1f" % DUR)
        .replace("__STAGES__", STAGE_JSON)
        .replace("__TITLE__", TITLE)
        .replace("__SUB__", SUB)
        .replace("__REF__", REF_IMAGE.replace(" ", "%20") if REF_IMAGE else ""))
open(TS_NAME, "w", encoding="utf-8").write(
    "// AUTO-GENERATED by svg-redraw scripts/emit.py - do not edit by hand.\n"
    "export const %s_SVG = " % TS_EXPORT + json.dumps(SVG, ensure_ascii=False) + ";\n"
    "export const %s_DURATION = %r;\n" % (TS_EXPORT, DUR) +
    "export const %s_W = %d;\nexport const %s_H = %d;\n" % (TS_EXPORT, W, TS_EXPORT, H) +
    "export const %s_STAGES = %s as {key: string; label: string; from: number; to: number}[];\n"
    % (TS_EXPORT, json.dumps(json.loads(STAGE_JSON), ensure_ascii=False)))
for f in (HTML_NAME, DEMO_NAME, os.path.join(OUT, "art_%s.svg" % TAG), TS_NAME):
    print("%9.1f KB  %s" % (os.path.getsize(f) / 1024.0, f))

