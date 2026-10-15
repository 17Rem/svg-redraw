# Evidence-based tuning

Keep a high-detail original-resolution candidate before trying optimizations. Change a
setting to address a visible symptom, compare at normal viewing size and in important
crops, and retain the version that better matches the reference. Global pixel error alone
cannot decide whether expressions, lettering, or optical effects are correct.

## Original-resolution Rem refinement case

The newer case used the actual 3840 × 2188 PNG, blue hair, dark/white clothing and subtle
skin shading. Keeping 8-bit color and zero speck filtering, layer difference 8 produced
87,581 paths, difference 4 produced 110,117, and difference 1 produced 145,026. The selected
version also replaced measured background color bands with a radial gradient and restored
soft face color inside its existing base contour. A 0.6-unit SVG edge blur was retained
after checking the output. The final artwork was about 32 MB in that implementation.

Within that run, full-image MAE fell from about 1.346/255 for its initial candidate to
0.730/255 after refinement; the selected face crop fell from about 3.670 to 2.737/255.
These compare candidates from the same run, not the old skill against the new skill under
controlled conditions. They are supporting evidence, not a perceptual similarity score.

The main transferable decisions are: use the original file, preserve color detail, handle
observed continuous fields with native gradients, and inspect aligned local crops. Do not
make 145,000 paths, the Rem coordinates, a fixed blur radius, or a particular global score
targets for another image. A compact/editable SVG remains a different user priority.

## Earlier pale illustration case

The motivating run used a 960 × 1720 JPEG anime illustration with pale silver hair,
small music notation, jewelry, and a prism rainbow. Its selected VTracer configuration was:

```text
colormode=color hierarchical=stacked mode=spline filter_speckle=0
color_precision=8 layer_difference=8 corner_threshold=60
length_threshold=3.5 max_iterations=10 splice_threshold=45 path_precision=2
```

After removing 268,860 empty paths, 122,608 nonempty artwork paths remained. Temporary
construction and contour paths brought the demo count to 124,447. The HTML was about
29 MB. At the source dimensions the rendered candidate measured MAE 4.808/255 and
RMSE 12.305/255; 4.18% of pixels had at least one channel error greater than 25. It was
visually close, not pixel-identical. These figures are observations from this image and
renderer, not quality gates or promises for future images.

Tested alternatives included lower color precision, small-region filtering, doubled
resolution, polygon contours, and a quantized contour reconstruction. Some reduced file
size or changed the texture but visibly damaged details or the rainbow. The doubled-size,
7-bit polygon candidate broke the pale rainbow near its far end. Do not conclude that
upscaling or polygon modes are always worse; reject them when that failure is observed.

## Decisions driven by symptoms

| Observation | Useful next experiment |
|---|---|
| Missing stars, jewelry, narrow letters | Restore zero speck filtering/full color precision; inspect the exact crop. |
| Ragged line edges | Compare another curve mode or resolution while holding other settings steady. |
| Banding or vanished pale spectrum | Restore color detail; compare the original-size baseline before adding smoothing. |
| Huge path count | Count and remove empty `d` paths first; nonempty tiny geometry may be real detail. |
| Webpage too slow | Reduce redundant style writes, keep static output available, and segment video export before simplifying geometry. |
| Face looks wrong | Locate the trace defect; do not cover it with a generic replacement eye or mouth. |
| Metrics improve but an important feature worsens | Prefer the correct feature or continue with a focused change; do not use the global score as a pass. |

Once checks pass, do not run an arbitrary search of parameter combinations. A smaller or
more editable SVG is a separate tradeoff from maximum fidelity and should follow the
user's priority. Do not claim this process universally outperforms other tracing methods:
the original skill and new process were not benchmarked under controlled equal conditions.
