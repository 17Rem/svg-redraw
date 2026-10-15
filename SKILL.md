---
name: svg-redraw
description: Faithfully reconstruct a supplied illustration as native SVG and offline HTML, with measured gradient refinement, an interactive color/comparison/code studio, and a local drawing-process video when requested.
---

# Reference illustration to SVG Studio

Use the reference as the visual authority. Work at its actual file dimensions, retain
fine color regions, inspect critical crops, and correct observed defects with measured
native SVG geometry or gradients. The process is vector reconstruction plus targeted
refinement. Describe the replay as a staged reconstruction, not a recording of hand-drawn
strokes or a recovery of the original artist's layers.

## Output boundaries

- The finished SVG and standalone artwork HTML contain native geometry, gradients and
  filters only. Keep the reference aspect ratio and `viewBox`. No Canvas, `<image>`,
  raster data URLs, external assets, frameworks or fonts in the artwork.
- Add a drawing studio and video when requested. The studio contains the complete SVG
  inline and works from a local file without a server, Node or Python.
- When the user asks for reference comparison, the studio may read a **separate local
  reference file**, solely in comparison panels. Use `emit.py --comparison` and include
  that file in the offline bundle. Otherwise omit reference images entirely. Never put
  the comparison image inside the finished artwork.
- Preserve the original and keep build files separate. Use available runtimes and
  task-local authoring packages. Do not install dependencies into the delivered HTML.

## Reconstruct and refine

Commands and per-image configuration are in [references/pipeline.md](references/pipeline.md).

1. Inspect the original file's dimensions, alpha, composition and sensitive areas: eyes,
   hair, hands, lettering, thin lines, skin tones, transparent effects and gradients.
   A chat thumbnail or previously resized JPEG is not the full-resolution source.
2. Use `trace.py` at original dimensions. `fidelity` is the high-detail default: color,
   stacked, spline, 8-bit color, zero speck filtering, layer difference 1. The `baseline`
   and `detail` presets use differences 8 and 4. Keep a baseline when investigating a
   visible problem; do not run every preset automatically when the result already works.
3. Remove empty paths only, preserving nonempty geometry and stacking. Lower merge
   thresholds retain more detail but can greatly increase file size and rendering cost.
4. Rasterize and compare at identical dimensions, both full-frame and in aligned critical
   crops. `render_check.py` supplies MAE/RMSE and comparison images. Large uniform
   backgrounds can dominate global scores; expressions and fine contours need inspection.
5. If smooth shading becomes flat or banded, refine the affected color field with native
   gradients clipped to the measured contour. Read [references/refinement.md](references/refinement.md)
   and use `refine_gradients.py` when its radial/surface models fit the image. Preserve
   facial features and overlying linework. A whole-face replacement or blanket blur is
   not the default. Keep refinements only after before/after comparison supports them.

Use [references/tuning.md](references/tuning.md) for measured examples, not universal
thresholds. Stop when requested quality is met or remaining trials no longer help.
Report material residual differences and never infer pixel identity from a successful tool.

## Build the studio and drawing timeline

`emit.py` and `demo_template.html` implement the current studio. Use measured per-image
parts, rule bounds, optional color/area conditions, and construction guides; never copy
another character's coordinates into the new picture.

- Keep final paint order. Adjacent stage/part wrappers add metadata without changing
  occlusion. Existing native gradients, clipping and filter containers remain intact.
- Organize replay as construction → contours → base colors → shadows → details →
  highlights. Omit empty stages and temporary marks from the finished artwork. Use each
  part/phase's own vertical extent for reveal, and remove reveal clipping at completion.
- Show semantic layers, zoom/fit/part focus, play/pause/replay, seeking and speed controls.
  Fit the actual canvas to available width **and height** so the bottom is not cropped.
- Link the active part to the palette, selected element and code. Colors and HEX/RGB
  values come from actual fills or gradient stops. Copy the full element even when the
  preview is truncated; include its gradient definition when relevant.
- When enabled, show identically positioned reference and SVG crops, plus an enlarged
  comparison dialog. Automatically follow the current part; manual inspection may turn
  following off. Never use the reference as a substitute for an unfinished SVG preview.
- Keep `drawingPlayer.setTime(seconds)`, `play`, `pause`, `duration`, and `time` available
  for deterministic seeking. Keep selection, palette and code in sync when seeking too.

Run `verify_studio.cjs` and inspect its screenshots. Check part/gradient selection, final
frame, colors, copying, layer visibility, playback, mobile fit, and no page errors or
network dependencies. Also raster-compare the emitted static SVG with the selected
refined SVG: the UI wrapper must not introduce a visual change.

## Export the requested video and bundle

Read [references/video.md](references/video.md). `record_studio.cjs` records the actual
studio, including live comparison, colors and code; `render_video.cjs` captures exact
seek times in resumable segments when dense SVG or recording limits require it. Both
support the studio or artwork-only view and explicit playback speed. Use the same demo
timeline rather than a separate approximation of the drawing sequence.

Validate duration, dimensions, full decode and beginning/middle/end frames. Distinguish
output FPS from distinct captured frames. Save the MP4 where the user requested it and
include completed files in a requested offline ZIP. Do not claim a video was generated
because a filename exists.

The older `geo.py`, `fast.py`, `overlay_example.py` and `remotion/` resources are retained
legacy material, not steps in this workflow. Consult [references/pitfalls.md](references/pitfalls.md)
for observed failures. The updated workflow does not require a subagent or additional
approval for ordinary authorized local generation.
