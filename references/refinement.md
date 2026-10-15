# Measured native gradient refinement

Read this only when a traced candidate visibly loses a smooth color field. The purpose is
to restore observed shading without replacing the subject's contours, expression or linework.
Keep the unmodified trace and compare full-frame plus the affected crop after every change.

`refine_gradients.py` accepts the direct-path trace, its same-size raster, the reference,
and the per-image `drawing.json`. It emits another **native SVG** plus a source/config hash
report. The generated objects are gradients, stops, rectangles, clipping paths and optional
small SVG blurs. It embeds no image or pixel array.

## Radial fields: broad smooth backgrounds

Use this model when unobstructed equal-color contours support an elliptical radial field.
Measure the center and radii from several contours, not from the image center by default.
Sample rectangles must contain the original background without hair, clothing or text.

Schema fragment (coordinates below describe a hypothetical 400 × 300 source):

```json
{
  "refinements": {
    "radial": [{
      "id":"background-light", "part":"background", "phase":0,
      "replacePart":"background",
      "center":[200,150], "radii":[200,150],
      "sampleRects":[[0,0,70,300],[330,0,400,300]],
      "sampleRange":[0.65,1], "sampleWindow":0.01,
      "sampleBins":80, "stops":81, "stride":1,
      "extrapolateInner":false
    }]
  }
}
```

The helper measures median RGB at normalized radii and interpolates native gradient stops.
`replacePart` removes only direct paths assigned to the named part by this image's rules,
and places the replacement background before the retained artwork. Inspect this assignment
before using it: an overly broad background rule could remove part of the subject. The
report lists every removed source index. Omitting `replacePart` keeps all existing paths.

Unobserved inner radii clamp to the nearest measured color by default. Enable
`extrapolateInner` only with evidence that a continuation is appropriate (for example,
the unobserved area is hidden by an opaque subject). Optional `extrapolateFitUntil`
controls the measured radial interval used for that continuation. Do not infer an unseen
highlight or invent a new halo just to make the background prettier.

## Surface fields: soft skin or fabric color

Use a surface model when a large traced base fill lost subtle shading but its outline is
already correct. Select the exact base path in the cleaned source SVG. `clipSourceIndex`
is its zero-based root-child index, not a path number from an older trace or an emitted
studio. A changed trace may require a new index; the helper checks its base fill.

```json
{
  "refinements": {
    "surfaces": [{
      "id":"skin-soft-tone", "part":"face", "phase":0,
      "clipSourceIndex":12, "baseFill":"#FCF2F1",
      "bbox":[120,80,280,240],
      "matchTolerance":0,
      "sampleColor":[{"coefficients":[1,0,0],"min":240}],
      "sigma":4, "fallbackSigma":16,
      "step":[8,6], "bandBlur":2
    }]
  }
}
```

These are schema values, not presets for every face. Choose radii and spacing relative to
the reference's actual scale and softness. Sampling is limited to pixels where the raster
of the selected trace exposes that base fill; optional RGB conditions exclude other materials.
The helper estimates the local color field, expresses it as horizontal linear-gradient
bands, and clips the group to the original base path. It inserts the group immediately
after that path so later eyes, lashes, mouth contours and cell shadows retain their order.
The larger fallback kernel fills unobserved portions of the base field; verify that those
areas are occluded or visually supported rather than relying on interpolation blindly.

The original Rem case used 29 bands over a 580-pixel-tall region, sampled at 25-pixel
horizontal spacing. This is a smooth field model, not permission to reproduce an image
as millions of colored rectangles. Avoid unnecessary bands when fewer native gradients
represent the observed field faithfully.

## Edge softness is optional

`refinements.edgeBlur` applies a native SVG Gaussian blur to the selected artwork, measured
in original SVG units. It defaults to zero. The Rem test retained 0.6 at 3840 × 2188 after
comparison; that value is not a universal setting. Softening can erase eyelashes, lettering
or highlights, especially on small images. Compare the actual SVG filter output, not an
unrelated rasterizer's bitmap blur with the same numerical radius.

If these two models do not fit the reference, author another small native correction from
measured geometry and colors, document it, and compare it. Do not force every illustration
through radial-background and skin-field assumptions.
