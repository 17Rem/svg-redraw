# svg-redraw

Turn a reference image into a **layered, native-SVG redraw** — plus the artifacts that prove it:

- a **self-contained HTML** file (HTML + CSS + SVG, no Canvas, no embedded bitmap, no external resources),
- a **drawing-process demo page** you can play, scrub and rewind,
- optionally a **drawing-process video** rendered with Remotion.

Not an auto-trace to a single flat path soup: the output is organised the way an illustrator
works — construction lines, background, flat colour, shadow, deep shade, highlights, hairlines,
ink, face, effects — and every stage is separately addressable so it can be replayed.

```text
paper → sketch → bg → base → shadow → deep → light → line → ink → face → fx
```

## What makes it different from "posterise + trace"

A naive colour-quantise-and-trace pipeline produces a mosaic. This one is built around the
failure modes that actually show up on real illustrations:

| Problem | What this does |
|---|---|
| Ink lines turn into dotted confetti | lineart is extracted **separately** with a black-hat filter and drawn as its own layer above the fills |
| Anti-aliased edges poison the palette | the ink band is **inpainted away** before k-means, then fills continue underneath the strokes |
| Staff lines, monograms, lace vanish | speck merging is **colour-aware** — a small patch is only absorbed when it nearly matches its neighbour |
| White fabric ends up in the highlight stage | classification is relative to a **wide-window median** base tone, not local extremes |
| Every thin stroke renders dashed | regions are emitted as **polylines**, never splines — a cardinal spline self-intersects on a 1–3 px stroke and cancels itself under the nonzero fill rule |
| Pale cracks between neighbouring fills | each path carries a same-colour hairline stroke that seals the seam without eating detail |

The details, and the twelve real bugs behind them, are written up in
[`references/`](references/): [pipeline](references/pipeline.md) ·
[tuning](references/tuning.md) · [pitfalls](references/pitfalls.md).

## Requirements

- **Python 3.10+** with `numpy` and `Pillow`. Nothing else — the morphology, contour walking
  and simplification are implemented in `scripts/geo.py`.
- **A Chrome/Chromium binary** for the quality gate. Remotion's bundled headless shell works,
  a normal Chrome install works; detection is automatic or pass `--chrome <path>`.
- **Optional:** a [Remotion](https://remotion.dev) project for the video step.

## Install

Skills are discovered from `<root>/<name>/SKILL.md`. Clone this repository into whichever
root your agent scans — for example:

```bash
# agent-specific
git clone https://github.com/<you>/svg-redraw ~/.agents/skills/svg-redraw

# or per project (highest priority, travels with the repo)
git clone https://github.com/<you>/svg-redraw <project>/.dsh/skills/svg-redraw
```

## Use

```bash
SK=~/.agents/skills/svg-redraw/scripts
REF="reference.jpg"

# 0. look before you trace: size, palette, and gridded zoom crops to measure from
python "$SK/analyze.py" --src "$REF" --out build/crops \
    --crop "head:330,30,700,400" --zoom "eye:490,200,580,270:6"

# 1. vectorise (~3 min for 960x1720)
python "$SK/trace.py" --src "$REF" --out build --tag a \
    --k 72 --minpx 6 --eps 0.55 --speck 14 --colthr 22 --line-thr 17 --dark 60 --maxw 6
#    -> build/trace_a.json, build/mask_ink_a.png  (open the mask: it should read as pencil art)

# 2. score it against the reference
python "$SK/render_check.py" --svg build/art_a.svg --ref "$REF" --out build \
    --crops "380,180,600,340"

# 3. optional hand-drawn layers (eyes, mouth, construction lines)
cp "$SK/overlay_example.py" overlay.py     # then replace its coordinates with measured ones

# 4. emit the deliverables
python "$SK/emit.py" --trace build/trace_a.json --out build --html-out . \
    --name my-art --title "MY ART" --duration 88 --overlay overlay.py --ref-image "$REF"
```

`emit.py` writes `my-art.html`, `my-art-demo.html`, `build/art_a.svg` and a
`my_art_art.ts`-style module for the video step. The demo page supports
`#t=25` to seek and `#t=25&ref=1` to open with the reference-comparison panel on.

### Video

Copy `scripts/remotion/RedrawVideo.tsx` into your Remotion project, point it at the generated
module, register a composition at `width 1920 / height 1080` for
`(duration + 8) * fps` frames, then:

```bash
npx remotion render MyArtDrawing out/my-art-drawing.mp4 --codec=h264 --crf=18 --concurrency=2
```

Always render `--frames=0-119` first and check the first two seconds: if the artwork is
already complete, you hit the detached-subtree bug described in `references/pitfalls.md` §3.

## Quality gate

`render_check.py` reports the mean absolute difference against the reference. On a dense
illustration (960×1720, ~12 000 paths, ~4.5 MB HTML):

| Measurement | Value |
|---|---|
| Palette ceiling (same colours, rasterised) | ≈ 2–3 |
| Final vector result | ≈ 6–8 mean\|d\|, 7–9 % of pixels off by >25 |
| Runtime | ~3 min trace, ~1 min emit |

The gap between the two numbers is the vectorising step, and it is almost entirely 1–2 px
line-art edges — no polygon approximation reaches zero there. **Use the ceiling:** if your
palette scores 2.5 and the vector result scores 12, the palette is fine and no `--k` will
help; work the symptom table in `references/tuning.md`.

## Compliance, if your brief forbids bitmaps

The static page and the SVG contain `<img>` = 0, `<canvas>` = 0, `base64` = 0, external
scripts/stylesheets = 0 — the only URL in the file is the SVG namespace. The demo page has
exactly one optional `<img>`, the reference panel, which loads a sibling file by relative path
and only after the reader asks for it.

## Responsible use

This tool reproduces an image you give it. **You are responsible for having the rights to that
image.** Tracing a copyrighted illustration and republishing the result is a derivative work;
"it is now vector data" does not change that. No example artwork is bundled with this
repository for exactly this reason — use your own images, public-domain material, or images
whose licence permits derivatives.

## License

MIT — see [LICENSE](LICENSE).

## 中文速览

把参考图重绘成**原生 SVG**：分层（构图 → 背景 → 固有色 → 阴影 → 暗部 → 高光 → 细线 →
墨线 → 面部 → 光效），输出自包含 HTML、可播放绘制流程的 Demo 页，以及可选的绘制过程视频。
不含 Canvas、不嵌位图、不依赖外部资源。

**与"取色描边"的区别**：线稿单独提取（black-hat）并压在色块之上；做色板前先把墨线
inpaint 掉；碎点合并认颜色，所以五线谱、字母之类的细节不会丢；明暗用局部中位亮度分类，
白布料不会被误判成高光；轮廓输出**折线而非样条**，避免细线被自交填充打穿成虚线。

**要求**：Python 3.10+（仅需 numpy / Pillow）+ 一个 Chrome/Chromium（渲染比对用）。

完整流程见上方命令；参数与踩坑记录在 [`references/`](references/)。
**请只使用你有权处理的图片** —— 描摹受版权保护的插画并公开发布属于演绎作品。
