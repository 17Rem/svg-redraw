# Pitfalls — the bugs that cost real time, and their fixes

Everything here was hit for real while building this pipeline. They are listed in the order
they tend to bite.

## 1. Splines punch holes in thin strokes

**Symptom.** Every thin line renders as a dotted / dashed chain, while `mask_ink.png` shows a
perfectly continuous stroke. Fills develop unexpected holes. It looks like a z-order or a
mask problem, so you go and debug the wrong thing for an hour.

**Cause.** A Catmull-Rom / cardinal spline through the boundary of a 1–3 px wide shape
overshoots the boundary. The curve self-intersects, and under `fill-rule="nonzero"` the
opposite windings cancel — the fill is subtracted exactly where the stroke is thinnest.

**Fix.** Emit `M/L/Z` polylines. Compensate with a slightly tighter RDP tolerance and 1–2
passes of the 3×3 averaging kernel. You get smoother-looking curves *and* a smaller file
(`L` is a third the length of `C`).

**How to recognise it early.** Render the ink layer alone and zoom. If the mask is
continuous but the render is dashed, it is this bug, not a threshold.

## 2. Attribute injection destroys self-closing tags

**Symptom.** Two or three elements of a hand-authored overlay render, and everything after
them silently vanishes. No console error. The SVG is "valid enough" to parse.

**Cause.** The emitter injects `data-t` / `data-d` into every tag with a regex that appends
before the final `>`:

```python
m.group(0)[:-1] + ' data-t="..." data-d="...">'
```

For a self-closing `<ellipse ... />` that produces `<ellipse ... / data-t="...">`. In the
HTML parser's foreign-content mode the `/` is only a self-closing marker when it is
*immediately* before `>`, so the tag is treated as an open element and **every following
sibling becomes its child** — and children of an `<ellipse>` are never rendered.

**Fix.**

```python
if tag.endswith("/>"):
    return tag[:-2] + attr + "/>"
return tag[:-1] + attr + ">"
```

**Defence.** After emitting, grep the output for `/ data-t` — there should be zero hits.

## 3. Remotion styles detached SVG nodes

**Symptom.** The whole video renders with **every frame showing the finished artwork**. The
single-frame `still` command is correct; the full `render` is not. Re-rendering "to be sure"
does not help.

**Cause.** The player keeps a cached array of element references and writes `opacity` onto
them each frame. Inside a reused browser tab Remotion can rebuild the injected SVG subtree
between frames, so the cached references point at nodes that are no longer in the document.
Writing to detached nodes is a silent no-op, and the *live* nodes keep their default
`opacity: 1`.

**Fix.** Re-bind whenever the cache has gone stale, and re-apply on both effect passes:

```tsx
if (!nodes || !nodes.length || !nodes[0].el.isConnected ||
    nodes[0].el.ownerSVGElement !== root) {
  nodes = collect(root);
  cacheRef.current = nodes;
}
useLayoutEffect(paint);   // no dependency array: runs after every commit
useEffect(paint);         // catches a subtree rebuilt after paint
```

**Verify cheaply.** Render `--frames=0-119` first and extract a few frames. If frame 2 is not
nearly blank paper, stop and fix this before spending 30 minutes on the full render.

## 4. Debug text that lies

Related to the above: a value written into a ref *inside* an effect and read during render is
always one render behind. A still at frame 121 printed `no-effect` while the artwork was in
fact styled correctly. Verify with **the image**, not with a self-reported counter — or
report the value through state, not a ref.

## 5. Colour-blind speck merging eats the details

**Symptom.** The posterised palette is a near-perfect match (mean|d| ≈ 2), yet the final
trace is missing staff lines, monograms and lace, and scores ≈ 10.

**Cause.** "Merge every component below N px into its dominant neighbour" is fine for JPEG
noise and fatal for 1–2 px intentional detail. A white staff line on a navy skirt is a small
component; it gets absorbed into the navy.

**Fix.** Only absorb when `colour_distance(component, neighbour) < colthr` (≈ 15–22). Keep a
second, colour-blind pass strictly below `--minpx` to guarantee coverage. Then compare the
result to the palette ceiling: the gap between them is your real quality loss.

## 6. `minpx` / merge-limit gap leaves holes

**Symptom.** Pinprick white dots scattered over dark regions. They are the paper showing
through.

**Cause.** Patches between the merge limit and `--minpx` survive in the label map but are
dropped when regions are extracted, so those pixels belong to no path.

**Fix.** Keep the merge limit ≤ `--minpx`, and finish the merge loop with a pass that absorbs
*everything* still below `--minpx` regardless of colour. Coverage is worth more than the
exact colour of a 4 px patch.

## 7. Local max/min classification puts white fabric in the highlight stage

**Symptom.** Mid-video the artwork is a colander of white holes; the white cloth appears only
at the very end, in the highlight stage. The finished frame is fine, so it only shows up in
the animation.

**Cause.** `rel = (lum − local_min) / (local_max − local_min)` over a small window measures
"contrast with the neighbourhood", not "is this lighter than the local base colour". White
silk surrounded by navy scores ≈ 1.

**Fix.** Compare against a **wide-window median** (21 px) instead: `ratio = lum / median`.
Large light areas score ≈ 1 and become `base`; genuinely bright accents on a dark ground
still score high and stay `light`.

## 8. Hairline cracks between neighbours

**Symptom.** A pale spiderweb over dark areas at high zoom; it reads as "unfinished".

**Cause.** Every region is RDP-simplified independently, so shared edges stop agreeing.

**Fix.** Same-colour stroke ≈ 1.2 px on each path. Prefer it to dilating masks by 1 px: a
1 px dilation lets a later-drawn neighbour take 1 px from each side of an earlier thin
detail, which can erase a 2 px line completely.

## 9. Zone by connectivity alone

**Symptom.** Background decoration (a moon, a beam) is drawn in the character's stage order,
or the character's stage order swallows the sky.

**Cause.** Flood-filling "near white connected to the border" gives you the *paper*, not the
*character*. Anything touching the subject — a light beam from an eye to the frame edge —
joins the same connected component.

**Fix.** Build an explicit character mask: threshold `dist_white > char_thr`, dilate, keep
the largest component, fill its holes, erode back. Classify each patch by overlap with that
mask (`> 0.55` character, `< 0.15` background, else a boundary patch).

## 10. The demo page's compare panel must not be embedded

**Trap.** The obvious way to add "put the reference beside it" is `<img src="data:...">`.
That is exactly what the brief forbids.

**Fix.** Keep the artwork pure. Ship the comparison as an *opt-in panel* that loads a
sibling file by relative path only when the user clicks the button (and hide the button when
no file name was configured). The static page and the SVG stay at `<img>` = 0, `base64` = 0.

## 11. HTML-escaped `<` in generated markup

`emit.py` currently builds `<style>` blocks with `>` only, so no escaping is needed — but if
you ever inline a script or style string containing `<`, HTML mode will reinterpret it. Keep
generated markup attribute-only, or escape the payload.

## 12. Committing to a long render too early

A 2880-frame render at 1920×1080 with a 4.5 MB inline SVG takes 20–35 minutes. Always:

1. `still` at three or four frames spread across the timeline;
2. `render --frames=0-119` and check frame 2 / 60 / 118;
3. only then the full render.

Step 2 catches bug #3, the classification trap (#7) and a broken overlay (#2) for the cost of
one minute.
