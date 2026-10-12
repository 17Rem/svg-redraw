# Tuning — parameters, symptoms, and the iteration recipe

## Parameters

### `trace.py`

| Flag | Default | What it controls | Raise it when | Lower it when |
|---|---|---|---|---|
| `--k` | 64 | palette clusters | gradients band (skies, drapery) | the file is too big / specks multiply |
| `--minpx` | 6 | smallest traced patch | speckle noise everywhere | thin details are missing |
| `--eps` | 0.55 | RDP tolerance for large patches | curves look faceted* | curved contours look polygonal |
| `--speck` | 14 | merge limit for near-identical specks | noise persists | details disappear |
| `--colthr` | 22 | max RGB distance for a speck to be absorbed | dark areas still noisy | white/contrast details vanish |
| `--line-thr` | 12 | black-hat threshold for ink | the ink mask is a grey web | strokes are broken/dotted |
| `--dark` | 30 | "darker than local blur" ink test | soft shading is being inked | real dark lines are missed |
| `--maxw` | 7 | reject ink components wider than this | big dark shapes are inked (muddy) | thick outlines vanish |
| `--char-thr` | 100 | distance-from-white for definite character pixels | background decoration is treated as the subject | thin subject parts are dropped |
| `--soft-lum` | 175 | strands lighter than this get thinned 1 px | hair-over-face lines look like ink | they disappear |

\* Note `--eps` is only the *base*; the per-patch tolerance is
`eps · clamp((area/500)^0.5, 0.30, 1.5)`, so small patches are always traced tightly.

### `emit.py`

| Flag | Meaning |
|---|---|
| `--duration` | seconds of the drawing timeline. 60–100 s is comfortable; below 40 s the early stages flash past. |
| `--stroke` | same-colour stroke width that seals hairline cracks. 1.0–1.3. Above ~1.6 total ink coverage gets heavy and `mean|d|` starts rising again. |
| `--plate` | paper colour. Sample the reference's border, do not use pure white unless the reference is white. |
| `--overlay` | path to the hand-layer module. Omit for a trace-only result. |
| `--ref-image` | file name used by the demo's optional comparison panel. Omit to hide the button. |

Stage weights live in `emit.py`'s `STAGES` list. Keep `sketch` ≥ 0.06 and `ink` ≥ 0.15 of the
total or the animation reads as "already finished, then refining".

## Symptom → cause → fix

| Symptom | Almost always the cause | Fix |
|---|---|---|
| Whole image looks washed out / milky | large light regions classified as `light`, drawn late, covering structure | classification must use the wide-window **median** base tone (see `pipeline.md` §5) |
| Thin lines render as **dotted / dashed** chains | a spline (Catmull-Rom) is being used instead of a polyline | emit `M/L/Z`; see `pipeline.md` §6 |
| White pinprick holes all over dark areas | merge limit < `--minpx`, so patches are kept in labels but dropped at tracing | set the merge limit ≤ `--minpx`, and add a final colour-blind fill pass |
| Pale spiderweb cracks over dark areas | neighbours simplified independently, no stroke | paint each region with a same-colour stroke ~1.2 px |
| Staff lines / monogram / lace missing | speck merge is colour-blind and ate the contrast details | `--colthr` down to ~15–22; details differ strongly from neighbours |
| Face is a blur of blobs | iris/lash are 30 px of deliberate design, beyond what a palette can hold | hand `FACE_SVG` overlay |
| Background bleeds into the subject | zone test uses connectivity only; decoration touches the subject | zone by overlap with a character mask built from `dist_white > char_thr`, dilated, largest component, holes filled, eroded back |
| Ink mask is a grey web | `--line-thr` / `--dark` too low | raise both; re-open `mask_ink_*.png` |
| Everything too dark / heavy | ink stroke width over-counted, or `--maxw` too high so masses got inked | lower `--maxw`; check the ink mask |
| File > 20 MB | splines, tiny `--eps`, `--minpx` too low | polylines + `--minpx 6` + integer-ish coordinates |

## The iteration recipe

1. **Palette ceiling.** Posterise the labels and diff against the reference. Expect **2–3**
   mean|d|. If this is bad, fix the palette (raise `--k`, check the inpaint actually ran)
   before touching anything else.
2. **Ink mask.** Open `mask_ink_*.png`. It must look like a pencil drawing. Tune
   `--line-thr` / `--dark` / `--maxw` here, in isolation.
3. **First full trace.** Expect **6–8** mean|d| / **7–9 %** > 25 on a dense illustration.
4. **Look at viewing size first** (`side_*.png` scaled to ~470 px wide). Only then look at
   crops. Optimising against crops leads to over-tracing artefacts nobody will ever see.
5. **Zoom the worst crop.** If it is the face, that is a hand-layer problem, not a tracing
   problem — stop turning knobs.
6. Re-run `render_check.py` after every change; keep the numbers in the notes so a regression
   is obvious rather than a matter of opinion.

## Budgets, measured on a 960×1720 anime illustration

| Metric | Typical |
|---|---|
| `trace.py` runtime | ~3 min (most of it in the per-label component walk) |
| Traced patches | ~10 000 fills + ~1 500 ink strokes |
| `trace_*.json` | ~5 MB |
| Final HTML (one file) | ~4.5 MB, 12 000 `<path>` |
| Browser first parse | 1–2 s |
| `mean|d|` vs reference | 6–8 |
| Remotion render, 2880 frames @1920×1080, `--concurrency=2` | 20–35 min |

If the HTML is much bigger than ~1 KB per path, look for splines creeping back in or an
`--eps` that is too small.

## Resolution

Trace at the reference's native resolution. Upscaling before tracing invents detail that is
not there and inflates the file; downscaling destroys exactly the 1–2 px line work you are
trying to preserve. Scale at *playback* time instead — a 960×1720 SVG rendered into a
1080×1920 video frame looks better than the trace itself, because the browser's downscale
hides the residual edge jaggedness.
