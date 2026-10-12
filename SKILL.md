---
name: "svg-redraw"
description: "Use when the user wants a reference image (anime illustration, poster, painting, product shot) redrawn as native SVG — pure <path>/<circle>/<rect>/<g> layers, no Canvas, no embedded bitmap, no external resources — delivered as a self-contained HTML file, a playable drawing-process demo page, and optionally a rendered drawing-process video. Covers the vectorising pipeline, the layer model that reads like a human painting order, the hand-authored sketch/face overlay layers, and the per-pixel quality gate that proves the result."
---

# SVG Redraw

Turn one reference image into a layered, hand-feeling SVG redraw plus the artifacts that
prove it: a self-contained HTML, a scrubbable drawing-process page, and a video.

The whole point is that the result is **native SVG geometry**, not a bitmap in disguise.
Every visible mark is a `<path>`/`<circle>`/`<rect>` inside semantic layer groups.

## When to use

- "把这张图重绘成 SVG / 纯矢量 / HTML" with a ban on Canvas, base64 and external links.
- "还原构图、比例、轮廓、颜色、线条粗细、质感和图层关系".
- "要有线稿、固有色、阴影高光这样的绘制流程", and a demo page or video that plays it back.
- Any brief that says *do not simplify, do not omit, do not invent* — that is the signal to
  trace faithfully and gate on a pixel diff instead of eyeballing.

Not for: logos/icon cleanup, chart generation, or redesigning the artwork. This skill
reproduces a given image; it does not author new art.

## Deliverables

| File | Content |
|---|---|
| `<name>.html` | The finished artwork. One complete file: HTML + CSS + SVG, `viewBox="0 0 W H"`, responsive via `preserveAspectRatio`. |
| `<name>-demo.html` | Same SVG plus a JS player: play/pause, scrub, 0.5–4×, replay, space bar, `#t=25` seek, optional reference-comparison panel. |
| `<name>-drawing.mp4` | Remotion render of the same timeline (1920×1080 landscape, reference beside the redraw). |

Compliance is non-negotiable and cheap to verify:

```powershell
# must be 0 / 0 / 0 / 0, and the only URL is the SVG namespace
([regex]::Matches($html,'<img')).Count
([regex]::Matches($html,'<canvas')).Count
([regex]::Matches($html,'base64')).Count
([regex]::Matches($html,'<script[^>]*src=|<link')).Count
```

The one allowed `<img>` is the *optional* reference panel in the demo page, which loads
`sibling-file.jpg` on demand and is off until the user clicks 对比原图. Never inline the
reference as base64 — that is the thing the brief forbids.

## Environment

```powershell
$py = "<the python.exe returned by load_workspace_dependencies>"
$chrome = "<path to chrome-headless-shell, or a normal chrome>"
```

Only `numpy` and `Pillow` are needed — both ship with the bundled runtime. No OpenCV, no
scipy, no potrace; `scripts/geo.py` implements the morphology and contour walking.

## Step 0 — read the reference before touching it

```powershell
& $py $sk\analyze.py --src "ref.jpg" --out build\crops `
    --crop "head:330,30,700,400" --crop "torso:330,330,720,720" `
    --zoom "eye:490,200,580,270:6" --zoom "mouth:455,285,545,325:8"
```

This prints the size, how much of the canvas is non-background at several thresholds, and
the palette; the crops come back with a pixel grid drawn on them. Do this first: the eye
and mouth coordinates you will need for the hand overlay must be **measured**, not guessed.
Guessing a face is the fastest way to lose a day.

## Step 1 — trace

```powershell
& $py $sk\trace.py --src "ref.jpg" --out build --tag a `
    --k 72 --minpx 6 --eps 0.55 --speck 14 --colthr 22 --line-thr 17 --dark 60 --maxw 6
```

~3 minutes for a 960×1720 image. It writes `build/trace_a.json` and `build/mask_ink_a.png`.
Open the ink mask immediately — it should look like a clean pencil drawing of the reference.
If it is a grey web, `--line-thr` / `--dark` are too low. If strokes are broken and dotted,
they are too high.

What it does, and why in that order, is in `references/pipeline.md`. The short version:

1. **Lineart**: black-hat of the greyscale picks out ink strokes; components wider than
   `--maxw` (or bigger than `--max-mass`) are rejected and left to the colour layer, because
   a large dark garment is pigment, not ink.
2. **Inpaint**: the ink band is diffused away so the colour layer is clean flat pigment.
   Without this the palette gets poisoned by anti-aliased edge tones.
3. **Palette**: k-means over the inpainted canvas; ink pixels then inherit the nearest label
   so fills continue underneath the strokes.
4. **Regions**: exact pixel-corner boundary walk → RDP → 3×3 smoothing → **polyline** output.

## Step 2 — tune against the numbers, not your taste

The single most useful diagnostic: **posterise the palette and diff it against the
reference.** That number is the ceiling your vectoriser can reach.

- Palette ceiling ≈ **2–3** mean|d| → the colours are right; any remaining error is the
  vectorising step.
- Final trace ≈ **6–8** mean|d|, **7–9 %** of pixels off by >25 → good for a dense
  illustration. The residual is almost entirely 1–2 px line-art edges, which no polygon
  approximation can zero out.
- Final trace ≫ 9, or big blotches/holes → **not** a palette problem. Go to
  `references/tuning.md` and work the symptom table; the usual culprits are a speck-merge
  that ate the details, or a spline replacing the polyline.

```powershell
& $py $sk\render_check.py --svg build\art_a.svg --ref "ref.jpg" --out build `
    --crops "380,180,600,340;380,1500,620,1700"
```

Look at `side_a.png` at **viewing size** first, then the crops. Judge at viewing size: a
little edge raggedness that is invisible at 100 % is not worth 4 MB of extra detail.

## Step 3 — hand layers (the part the trace cannot do)

Copy `scripts/overlay_example.py` next to your build dir, rename to `overlay.py`, and
replace its coordinates with measurements from the Step 0 zooms. It exports up to two
fragments:

- `SKETCH_SVG` — construction lines (head oval, face cross, shoulder/waist, garment
  silhouette, limb axes). Hidden in the static page, visible in the demo/video where it
  reads as the pencil stage.
- `FACE_SVG` — eyes, lashes, mouth, blush. Drawn **on top of** the ink layer, so it must be
  opaque where it should win. Keep the lash thin (3–5 px) and slightly translucent; a
  fat pure-black lash reads as a sticker glued on a soft traced face.

Both stages are optional — emit skips a layer whose constant is missing or empty.

## Step 4 — emit

```powershell
& $py $sk\emit.py --trace build\trace_a.json --out build --html-out . `
    --name my-art --title "MY ART" --subtitle "纯 SVG 重绘 · 绘制流程回放" `
    --duration 88 --overlay overlay.py --ref-image "ref.jpg"
```

Produces the two HTML files, `build/art_a.svg`, and a `<name>_art.ts` module for Remotion.
Layers, in draw order:

`paper → sketch → bg → base → shadow → deep → light → line → ink → face → fx`

Every element gets `data-t` (reveal time) and `data-d` (fade duration); the demo page and
the video both just drive `opacity` from those attributes, so the timeline lives in the SVG
and the players stay trivial.

Stage weights are in `emit.py`'s `STAGES`. Give `sketch` and `ink` real time — a
two-second sketch stage makes the video feel like it starts finished.

## Step 5 — video (optional but usually wanted)

```powershell
Copy-Item build\my_art.ts <remotion>\src\
# src/RedrawVideo.tsx  <- copy from scripts/remotion/RedrawVideo.tsx
# src/Root.tsx         <- add the Composition (duration = (DURATION + 8) * 30, 1920x1080)
& $node $remotion render RedrawVideo "<workdir>\my-art-drawing.mp4" --codec=h264 --crf=18 --concurrency=2
```

**Verify the first 120 frames before committing to a 30-minute render:**

```powershell
& $node $remotion render RedrawVideo build\head.mp4 --frames=0-119 --codec=h264 --crf=22 --concurrency=2
```

Extract a few frames and confirm the paper is empty and fills in gradually. If every frame
shows the finished artwork, you hit the detached-subtree bug — see `references/pitfalls.md`.

## Hard rules that briefs like this usually impose

- Native SVG elements only; no Canvas, no `<img>` of the artwork, no base64, no external
  fonts/scripts/stylesheets. System font stacks only.
- Keep the original aspect ratio and use `viewBox` + `preserveAspectRatio` so it scales.
- Split into meaningful, semantically named layers (`id`/`class`), not one flat `<g>`.
- The drawing process must read like a human workflow: construction → background → flat
  colour → shadow → deep → highlight → ink → face → effects.
- Do not simplify, omit or invent. When in doubt, trace it and let the pixel diff decide.

## References

- `references/pipeline.md` — what each stage does and why the order matters.
- `references/tuning.md` — parameter table, symptom→fix table, iteration recipe, budgets.
- `references/pitfalls.md` — the concrete bugs that cost real time, with the fix for each.
