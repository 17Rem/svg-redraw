# Observed failure modes

## Preserve final stacking

Animation phase and SVG painting order are different concepts. Reordering all paths by
phase changes which colors cover which contours. Keep source order and wrap only adjacent
compatible paths. At the end, compare the generated SVG raster against the selected trace
as well as the reference. A presentation wrapper should not silently change the artwork.

## Empty paths and microdetails

VTracer with speck filtering disabled can emit many empty `d` values. They inflate reported
counts and DOM cost without drawing anything. Remove those, preserve nonempty paths, and
record both counts. Do not interpret every tiny shape as removable noise.

When cleaning a large XML tree, collect retained children and replace the child list once.
Repeated `ElementTree.remove` calls over hundreds of thousands of children can be
quadratic and make an otherwise short trace appear stuck.

## Coordinate systems

Use dimensions from the selected trace/reference, not the motivating image's dimensions.
Clip windows belong in the same user-coordinate system as the paths. If experimenting with
an enlarged source, normalize the SVG geometry/viewBox deliberately before comparing or
passing it to the emitter; do not combine a doubled trace with undoubled region coordinates.

## Semantics are approximate

Bounding-box centers and local luminance estimate stage/region membership. They cannot
recover the artist's real object masks or workflow. Inspect partial frames. Large white
fabric should appear as base color; a hue-sensitive optical effect may need a region phase
override. Do not paint over the final face merely to make the animation easier.

## Dense SVG export

An uninterrupted Playwright export timed out around the middle of the motivating run.
The exact cause was not established. Short segments with fresh browsers succeeded.
Avoid assigning identical dynamic stylesheet text on every frame; do not present that
optimization as a proven diagnosis of the earlier timeout.

Use fixed seek times for deterministic sampled export; use the real-time recording helper
when showing the actual studio playback. Restart only the browser owned by the export
helper. Close the browser and encoder after failures; never kill all Chrome processes.
For sampled export, retry a failed capture once, then preserve completed segments on failure.

Resume segments only for the same source, timeline, render options, and encoding options.
Duration alone cannot identify a compatible cached segment. The current helper namespaces
its segment cache using a source/options fingerprint.

## Verify the video, not the filename

A failed encoder may leave an MP4 without a `moov` atom. Check with ffprobe and decode the
whole video. Inspect start, middle, and end frames. The output FPS can exceed capture FPS
through frame repetition; disclose the distinction if discussing cadence.

Inspect color as well as timing. In the Rem test, the Playwright WebM recording intermediate
shifted contrast with the available FFmpeg, and wall-clock trimming left loading frames.
The current recorder starts a PNG screencast after the UI is ready, converts color once,
and compares the decoded end frame with a browser screenshot. Neither a valid codec nor
a complete duration alone proves that the recorded image matches the webpage.

## Comparison panels and code inspection

The standalone artwork remains native-only. A requested comparison panel is a separate
UI feature: use a local reference copy outside the SVG, pack it with the demo, and keep
the same crop coordinate system on both sides. Without a comparison request, the emitter
omits image elements. The older unconditional ban on a comparison panel is obsolete.

Fit the central artwork against both available width and height. A width-only aspect-ratio
rule cropped the bottom of the first Rem studio at a shorter desktop viewport. The current
template measures the viewport and updates the frame on resize.

Select code from real elements. Gradient fills need the referenced gradient definition;
`url(#...)` is not a hex color. Copy the complete element, even if the preview is shortened.
Windows clipboard text can normalize LF to CRLF; compare normalized line endings in a
clipboard test rather than treating that as lost code.

When a user manually selects a part or color, stop automatic inspection following. Turning
following on must refresh the code even if the current timeline sample has not changed.
Keep paint order separate from the selection/UI order.

## Retired resources

The old ink-removal/inpainting/palette pipeline and Remotion composition are not used by
the current helpers. Retained legacy files exist for compatibility/history, not as alternate
instructions. Do not revive their automatic face replacement, fixed coordinates or claimed
universal error thresholds by following stale docstrings. Use the current studio's optional
local reference comparison instead of the old image-substitution behavior.
