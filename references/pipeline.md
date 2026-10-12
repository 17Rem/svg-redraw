# Pipeline — what each stage does and why the order matters

The whole design answers one question: **how do you get from a JPEG to a few thousand flat
paths that still look like the artist's drawing?**

The naive answer — "quantise the colours and trace every blob" — gets you a posterised
image, not a drawing. It looks mushy, the ink lines turn into dotted confetti, and thin
details like staff lines, monograms or lace simply vanish. Every stage below exists because
the naive version failed in a specific, reproducible way.

## 1. Lineart before colour

```
closing  = erode(dilate(grey, R), R)      # R = 2, morphological closing
blackhat = closing - grey                 # thin dark structures light up
ink_cand = (blackhat > line_thr) | (grey < blur(9) - dark)
```

A black-hat responds to anything *locally darker than its surroundings* and **thinner than
~2R px**. That is exactly the definition of an ink stroke.

Two rejections matter:

- **Width**: each candidate component gets `width = 2·area / perimeter`. Components wider
  than `--maxw` are large flat masses (a dark dress, a night sky) — pigment, not ink. Leaving
  them in the ink layer paints them twice and makes them muddy.
- **Mass**: anything over `--max-mass` px is also rejected, as a backstop for a big region
  that happens to have a ragged perimeter.

The output is one binary mask. **Look at it before you go further** (`mask_ink_a.png`): it
should read as a clean pencil drawing of the reference. This is the single cheapest sanity
check in the whole pipeline.

## 2. Inpaint the ink away

The colour layer must be *flat pigment*, but every edge in a JPEG is a gradient of
anti-aliased pixels between ink and fill. If you feed those to k-means you spend clusters on
muddy in-between tones and the flats come out dirty.

So the ink band (dilated by 2) is diffused away — each unknown pixel takes the average of
its known 8-neighbours, iterated until it converges (24 sweeps is plenty). The colour layer
is then a clean, line-free painting, and the ink goes back on top later.

## 3. Palette, then ownership

k-means over the inpainted canvas (`--k` clusters, k-means++ seeding, 20 iterations).

Two details that are easy to get wrong:

- **Sample the whole canvas, not just the subject.** Background washes, moons and skies are
  part of the drawing. If you exclude them the palette is spent entirely on the character
  and the background turns into banding.
- **Ink pixels inherit the nearest label afterwards**, by iteratively growing the label map
  into the ink band. Fills must physically continue underneath the strokes, otherwise the
  1 px of overlap between a stroke and its neighbour shows the paper through.

**Validate here.** Render `cent[labels]` as a PNG and diff it against the reference. This is
your ceiling: the source JPEG compacted to 64–76 flat colours usually lands at **2–3 mean|d|**.
If the final vector result is far worse, the palette is not the problem and no amount of
`--k` will help.

## 4. Speck removal that respects contrast

Real illustrations have both JPEG noise *and* 1–2 px intentional details: white staff lines
on a navy skirt, a monogram, sparkles. A plain "merge every component below N px" deletes
both, and the details are the ones you notice.

The rule used here: **absorb a small patch into its dominant neighbour only when the two
palette colours are nearly identical** (`--colthr`, default 22 in RGB distance). A noise
speck in a flat area is absorbed; a white line on navy is kept, because its colour is nowhere
near its neighbour's.

A second pass then guarantees coverage: every remaining patch below `--minpx` is absorbed
regardless of colour, so no region is dropped at extraction time and no holes survive.

The `--minpx` / `--speck` relationship is the classic trap: if the merge limit is *below*
`--minpx`, patches in the gap are kept in the label map but dropped when tracing, and you get
pinprick holes all over dark areas. Keep the merge limit at or below `--minpx`.

## 5. Classification: base / shadow / deep / light

The layer model is what makes the result read as a painting rather than a mosaic, and it is
also what makes the drawing-process animation meaningful.

The classification must be **relative to the local base tone**, not to the local extremes.
The first version used `rel = (lum - local_min) / (local_max - local_min)` over a 7×7 window.
That works in the middle of a big shape and fails everywhere else: white lace surrounded by
navy scores `rel ≈ 1` and is filed as a *highlight*, so all the white fabric of the dress
ended up in the highlight stage and the mid-video state was a colander of white holes.

The fix is a **wide-window median** (21 px) as the estimate of "the colour of this area":

```
ratio = lum(patch) / median(local_luminance, 21px)
ratio < 0.74  -> deep      最深的暗部
ratio < 0.90  -> shadow    一级阴影
ratio > 1.15  -> light     高光
otherwise     -> base      固有色
```

A big white apron's own interior dominates its window median, so it scores ≈ 1.0 → base.
White lace on a navy dress still scores high → light. That is the behaviour you want.

Thin dark patches (`width ≤ 3.2`, dark relative to local) are additionally filed as `line`,
a hairline structure layer that sits just under the ink.

## 6. Tracing: boundary walk, RDP, smoothing — and **polylines**

Each region mask is walked on pixel corners. Because every foreground/background side becomes
a directed unit edge with the interior on its left, the edges always form closed loops and
holes come out automatically with opposite winding — draw them with `fill-rule="nonzero"` and
you need no boolean operations at all.

Then: RDP simplify → one or two passes of a 3×3 averaging kernel → emit.

**Emit straight segments, not a Catmull-Rom spline.** This is the least obvious and most
important decision in the pipeline. A cardinal spline through the boundary of a 2 px wide
stroke overshoots; the path self-intersects; and under `nonzero` fill the windings cancel,
punching holes in the middle of the stroke. The symptom is unmistakable — every thin line
renders as a **dotted / dashed chain** while the underlying mask is perfectly continuous.

A smoothed polyline (RDP at ε ≈ 0.25–0.45 plus 1–2 kernel passes) cannot leave the mask
hull, and because `L` commands are three times shorter than `C` commands, it is *also*
smaller: swapping splines for polylines took the trace JSON from 16.7 MB to 5.0 MB with no
visible quality loss.

Simplification tolerance scales with patch size — small patches are traced tightly
(ε ≈ 0.25), large washes loosely (ε ≈ 0.45) — because a 0.4 px error is a big deal on a 2 px
staff line and irrelevant on a 300 px skirt.

## 7. Sealing the hairline cracks

Each region is simplified **independently**, so two neighbours that share an edge no longer
agree on it exactly. Rendered side by side they leave sub-pixel white cracks — the pale
spiderweb you see over a dark area at high zoom.

Two ways to close them:

- dilate every mask by 1 px before tracing (the region then overlaps its neighbours by 2 px);
- or trace the exact mask and paint each path with a **same-colour stroke of ~1.2 px**.

Prefer the stroke. Dilating by 1 px means a later-drawn neighbour eats 1 px from each side of
an earlier-drawn thin detail, which can erase a 2 px line entirely; the stroke only takes
0.6 px and the ink layer, drawn last, stays pixel-exact. Skip the stroke on patches thinner
than ~3.5 px so hairlines keep their true weight.

## 8. Z-order

Within the character: `base → shadow → deep → light → line → ink`, and **inside each kind,
largest area first**. Big flat shapes go down early; small details land on top and are not
covered by their own neighbours' strokes.

Background regions are drawn before all of it, sorted by area descending. Effects (a rainbow
beam, a prism flare) go last.

Note this ordering is about *occlusion*. The animation timeline is independent — it is stored
as `data-t` on each element and sorted top-to-bottom, so an artist-like "working down the
sheet" cadence does not force a bad z-order.

## 9. Hand layers

A traced palette will never draw convincing eyes: the iris, the catchlight and the lash are
30 px of deliberate design, and k-means sees them as four arbitrary blobs. That is what the
`FACE_SVG` overlay is for — opaque shapes on top of the ink, measured from zoomed crops.

Same for `SKETCH_SVG`: the construction lines are *not* in the reference, they exist so the
first seconds of the animation look like a person blocking in a pose.

## 10. Timeline

`emit.py` assigns every element a reveal time from its stage window and its rank when sorted
by `(y, x)`:

```
t0 = stage_start + rank^0.88 * (stage_span - reveal)
```

Both players (the demo page's JS and the Remotion composition) only read `data-t` / `data-d`
and set `opacity`. The timeline lives in the artwork, so adding a player is ~40 lines, and
seeking is exact.
