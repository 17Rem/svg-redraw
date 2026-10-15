# svg-redraw

The current workflow uses the original-resolution reference, detail-preserving color
tracing, measured native gradient refinement and local crop comparison. It produces
standalone SVG/HTML and, when requested, an editor-style SVG Studio and local MP4.

Start with [SKILL.md](SKILL.md). Commands, configuration, and dependencies are in
[references/pipeline.md](references/pipeline.md); measured tradeoffs and known pitfalls
are in the linked references. The artwork remains an approximation and the displayed
timeline is not a recording of the original artist's strokes.

Active tools: `trace.py`, `refine_gradients.py`, `emit.py`, `demo_template.html`,
`render_check.py`, `verify_studio.cjs`, `record_studio.cjs`, `render_video.cjs`, and shared
`svg_common.py` in `scripts/`. The older geometry, face-overlay,
and Remotion resources are retained but are not invoked by the active workflow.

See [LICENSE](LICENSE) for the existing license.
