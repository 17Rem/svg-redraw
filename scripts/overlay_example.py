# -*- coding: utf-8 -*-
"""TEMPLATE for the hand-authored layers. Copy next to your build dir, rename to
`overlay.py`, and replace every coordinate with measurements taken from
`analyze.py --zoom` crops of YOUR reference.

Contract with emit.py
---------------------
* `SKETCH_SVG` - under-drawing / construction lines. Drawn first (right after the paper),
  and hidden in the static page via `#layer-sketch{display:none}`; visible in the demo and
  in the video, where it reads as the pencil stage.
* `FACE_SVG` - the rendering pass that a traced palette cannot do convincingly: eye
  anatomy, mouth, blush. Drawn on top of the ink layer, so it must be OPAQUE where it
  should win. Put it under `id="layer-face"`.
* Both may be `""` - emit.py skips the stage when the constant is missing/empty.
* Only DIRECT children of the root `<g>` receive `data-t` / `data-d`, and nested `<g>` are
  walked too; keep the tree shallow so the reveal order stays readable.
* Every tag MUST be written as `<tag .../>` or `<tag ...>`, never `<tag ... />` followed by
  more attributes - emit.py injects attributes and relies on self-closing tags staying
  self-closing (see references/pitfalls.md).
* Coordinates are in reference-image pixels (viewBox 0 0 W H), not normalised.
* Gradients already exist in the artwork <defs> and can be referenced directly:
  `grad-iris`, `grad-iris-lower`, `grad-blush`, `grad-paper`, and the `paper-grain-f` filter.
"""

# --------------------------------------------------------------------------- sketch
# Construction lines: head/skull oval, face cross, eye axis, shoulder and waist lines,
# garment silhouette guides, limb axes, horizon. Dashed, low contrast, and *deliberately
# approximate* - they are scaffolding, not a second drawing.
SKETCH_SVG = '''<g id="layer-sketch" class="art-layer" data-layer="sketch" data-label="构图 · 起草"
     fill="none" stroke="#8ea6d8" stroke-width="1.5" stroke-linecap="round"
     stroke-dasharray="8 7" opacity="0.85">
  <g id="sketch-canvas" stroke-dasharray="4 8" opacity="0.7">
    <rect x="24" y="24" width="912" height="1672" rx="4"/>
    <path d="M24 1604 H936"/>
  </g>
  <g id="sketch-head">
    <ellipse cx="508" cy="226" rx="80" ry="96"/>
    <path d="M508 130 V322"/>
    <path d="M428 240 H588"/>
  </g>
  <g id="sketch-body">
    <path d="M392 456 C450 438 570 434 666 448"/>
    <path d="M398 648 C378 706 360 760 350 806 M640 634 C666 690 692 744 708 786"/>
  </g>
</g>'''

# --------------------------------------------------------------------------- face
# The single highest-value hand layer. Measure the eye box from a zoom crop, then build:
#   sclera (eye opening) -> upper-lid shadow -> iris + pupil + catchlights -> lash -> lid line
# Keep the lash thin (3-5 px) and slightly translucent: a pure-black thick lash reads as a
# sticker on top of a soft traced face.
FACE_SVG = '''<g id="layer-face" class="art-layer" data-layer="face" data-label="面部 · 刻画">
  <g id="face-blush" opacity="0.55">
    <ellipse cx="472" cy="297" rx="42" ry="20" fill="url(#grad-blush)"/>
    <ellipse cx="566" cy="286" rx="34" ry="17" fill="url(#grad-blush)"/>
  </g>
  <g id="eye-right">
    <path id="eye-right-sclera"
          d="M497 236 C500 229 509 224.6 520 224.6 C532 224.6 542 228 548 232.4
             C544 242 534 249.4 521 249.4 C509 249.4 500 244 497 236 Z"
          fill="#cfc9e2"/>
    <path id="eye-right-uppershadow"
          d="M497 236 C500 229 509 224.6 520 224.6 C532 224.6 542 228 548 232.4
             C542 231.6 536 227.4 521 227.4 C509 227.4 501 230 498.4 238.4 Z"
          fill="#a196c2" opacity="0.55"/>
    <g id="eye-right-iris">
      <ellipse cx="521" cy="236.4" rx="14.6" ry="11.6" fill="url(#grad-iris)"/>
      <ellipse cx="521" cy="236.4" rx="14.6" ry="11.6" fill="url(#grad-iris-lower)"/>
      <path d="M507.2 233.6 C510.4 226 530.6 225.4 534.6 233.6
               C529.6 228.4 512 228.4 507.2 233.6 Z" fill="#564f80" opacity="0.92"/>
      <ellipse cx="520.6" cy="236" rx="4.2" ry="6.0" fill="#463c63"/>
      <ellipse cx="520.6" cy="236" rx="2.5" ry="4.2" fill="#2f2846"/>
      <ellipse cx="514.6" cy="230.4" rx="2.7" ry="3.1" fill="#ffffff" opacity="0.8"
               transform="rotate(-24 514.6 230.4)"/>
      <ellipse cx="531.6" cy="244" rx="2.8" ry="1.8" fill="#ffffff" opacity="0.5"
               transform="rotate(-18 531.6 244)"/>
    </g>
    <path id="eye-right-lash"
          d="M496 238.6 C498 227.8 507.6 220.4 520 220.4 C534 220.4 545 224.8 550.4 231.8
             C547.6 232.4 543.6 230.2 538.6 228.4 C532.6 226.2 527 225.6 521 226
             C511.6 226.6 503 231.2 500 239.6 Z"
          fill="#443c60"/>
    <path id="eye-right-lowline"
          d="M500 239.8 C507.6 245.6 516 248.6 524.4 248 C532.6 247.4 539.4 243.6 544 237.6"
          fill="none" stroke="#9a92b4" stroke-width="1.1" opacity="0.45"
          stroke-linecap="round"/>
  </g>
  <g id="face-mouth">
    <ellipse cx="487" cy="300.6" rx="7.4" ry="3.6" fill="#e3a8af" opacity="0.4"/>
    <path d="M481 299.2 C486.6 296.2 493 293.6 498.6 292.8"
          fill="none" stroke="#8b7892" stroke-width="1.6" stroke-linecap="round"/>
  </g>
</g>'''
