# Commands and per-image configuration

Authoring uses Pillow, NumPy and VTracer; OpenCV supports provisional contours and optional
surface fitting. Node uses Playwright and an SVG rasterizer such as Sharp. Video uses
FFmpeg/ffprobe and Chromium. Discover installed runtimes (`load_workspace_dependencies`
when available), set task-local `PYTHONPATH`/`NODE_PATH` as needed, and use actual paths.
None of these are runtime dependencies of the delivered webpage.

## 1. Original-resolution trace

```text
python scripts/trace.py --src reference.png --out build/fidelity.svg --preset fidelity
```

Presets differ only in `layer_difference`: baseline 8, detail 4, fidelity 1. Explicit flags
override the preset. Defaults otherwise remain color/stacked/spline, precision 8, speckle
0, corner 60, length 3.5, 10 iterations, splice 45, path precision 2. A JSON report records
source hash, dimensions, package version, parameters, and empty/nonempty counts.

For an observed detail problem, retain and compare another candidate:

```text
python scripts/trace.py --src reference.png --out build/baseline.svg --preset baseline
python scripts/trace.py --src reference.png --out build/detail.svg --preset detail
```

Do not downsample the source or re-encode it as JPEG for convenience. Preview crops can
be smaller; the selected geometry should retain the original dimensions unless the user
chooses a file-size tradeoff.

## 2. Render and compare

```javascript
const sharp = require('sharp');
await sharp('build/fidelity.svg', {limitInputPixels:false}).png().toFile('build/fidelity.png');
```

```text
python scripts/render_check.py --ref reference.png --render build/fidelity.png --out build/check --crop face:120,80,280,240
```

Measure crop coordinates for the current image. The helper emits aligned comparisons,
an amplified difference image, and metrics. Dimensions must match. Transparent inputs use
an explicit common matte; inspect alpha independently when transparency matters.

## 3. Measure parts and guides

The example below is a schema illustration for a hypothetical 400 × 300 image, not a
reusable composition. Author a new `drawing.json` for the actual source:

```json
{
  "title": "Reference illustration",
  "paper": "#f5f7fc",
  "initialPart": "subject",
  "defaultPart": "background",
  "parts": [
    {"id":"background","name":"背景","bbox":[0,0,400,300],"icon":"◉"},
    {"id":"subject","name":"主体","bbox":[90,35,310,295],"icon":"◇"}
  ],
  "rules": [
    {"part":"background","minAreaRatio":0.3},
    {"part":"subject","bbox":[90,35,310,295]}
  ],
  "sketch": [
    {"id":"head-envelope","d":"M200 45 C150 45 150 125 200 140 C250 125 250 45 200 45Z"},
    {"id":"face-axis","d":"M200 45 L200 140"}
  ]
}
```

`bbox` always means `[x0,y0,x1,y1]` in original coordinates. Rules use the shape's
approximate bounding-box center; the first matching rule wins. With no explicit rules,
the smallest containing part wins. `defaultPart` handles unmatched geometry. A rule can
combine `bbox`, `minArea`, `maxArea`, `minAreaRatio`, `maxAreaRatio` and color conditions:

```json
{"part":"ribbon","bbox":[250,50,320,200],"maxArea":8000,
 "color":[{"coefficients":[1,-1,0],"min":12}]}
```

That condition means `R-G >= 12`; each listed condition must match. This supports measured
hue distinctions without baking a character's colors into the helper. Limit eye-specific
rules by area so a large blue hair shape centered near an eye does not become a face layer.

Optional part `phase` or selected element `data-phase` overrides automatic staging:
0 base, 1 shadow, 2 detail, 3 highlight. `data-part` explicitly assigns a native element or
compound group. `data-bbox` supplies measured bounds for a compound group or unsupported
transform; bounds affect staging only. Phase/part guesses do not recover original artist
layers. Inspect intermediate frames, especially large white cloth and disconnected shapes.

## 4. Optional measured refinement

When comparison shows gradient banding or lost soft color, use the native models described
in [refinement.md](refinement.md). Add `refinements` to the same image-specific JSON:

```text
python scripts/refine_gradients.py --svg build/fidelity.svg --ref reference.png --render build/fidelity.png --config drawing.json --out build/refined.svg
```

Render and compare the refined candidate before choosing it. This operation is optional;
the emitter can use `fidelity.svg` directly. Keep baseline and refined files separate.

## 5. Emit static artwork and the current studio

```text
python scripts/emit.py --svg build/refined.svg --ref reference.png --config drawing.json --out deliverables --name illustration --duration 90 --lineart --comparison
```

Use `--comparison` only when the user requests a reference comparison. It copies the
reference to `illustration-reference.<ext>` and adds local `<img>` panels **outside** the
artwork. Without the flag, there are no raster image elements in the demo; the inspector
shows a native SVG local preview. SVG and standalone artwork HTML never embed a reference.

Outputs: `illustration.svg`, `illustration.html`, `illustration-demo.html`, a report, and
the reference copy only when enabled. The static files exclude guides and contour overlays.
The demo opens directly from disk. Its drawing is fully inline and does not depend on
the MP4, a server, online fonts, or authoring packages.

The emitter accepts direct traced paths plus the native gradient/clipping/filter groups
created by the refinement step. It preserves their render order and inherited attributes.
It is not a general importer for arbitrary SVG applications or external CSS documents.

## 6. Check and deliver

```text
node scripts/verify_studio.cjs --html deliverables/illustration-demo.html --out build/ui-check --chrome "PATH_TO_CHROME"
```

The browser check exercises real pointer controls, crop selection, colors/code, full copy,
visibility, all phase transitions, zoom/fit, seeking, the comparison dialog and mobile
layout. Review the saved screenshots. Render the emitted static SVG and compare it with
the selected candidate too: grouping is allowed, unintended pixel changes are not.

Video commands and validation are in [video.md](video.md). For a requested ZIP, include the
demo, static SVG/HTML, completed MP4 and local reference only when comparison is enabled.
Keep build caches and authoring dependencies out of the ZIP. Extract into a fresh folder
and open the demo to catch missing relative assets.
