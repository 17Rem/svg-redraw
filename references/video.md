# Studio playback and local MP4 export

The demo is the source of truth for the video: the active part, code, color and comparison
must follow the same `drawingPlayer` timeline. Default studio view shows the editor UI;
`?view=artwork` hides the UI and fits the native SVG to the viewport. The HTML remains
interactive and independently playable after export.

## Actual browser recording

```text
node scripts/record_studio.cjs --html deliverables/illustration-demo.html --out deliverables/illustration-drawing.mp4 --chrome "PATH_TO_CHROME" --speed 2 --width 1440 --height 900 --view studio
```

This records the live browser while the full timeline plays, encoding directly to H.264 MP4.
Speed choices match the player: 0.5, 1, 2, 4. A 90-second timeline at 2× takes roughly
45 seconds plus short holds. The report records timeline length, playback speed, viewport,
source/reference hashes, end-frame color error and video metadata. Browser-dependent PNG
frames are sampled at 25 Hz and encoded at 30 fps, which can repeat frames. Do not describe
it as 30 distinct drawing updates per second.

The helper waits for the UI, fonts and reference to load, then starts a Chromium PNG
screencast before playing. This excludes loading frames without guessing a trim offset.
PNG frames undergo one explicit conversion to BT.709 limited-range YUV. The tested
Playwright WebM intermediate altered contrast with the available FFmpeg; bypassing that
intermediate fixed the observed color error. This does not require Playwright's FFmpeg
runtime or modifying its installation. Pass `--ffmpeg`/`--ffprobe` if they are not on PATH.
If live capture is unsupported, use sampled export below.

At completion the recorder holds an actual browser screenshot of the finished player.
This prevents a delayed final screencast event from leaving the video at 98 or 99 percent.

The recording job keeps a hidden working directory with start/end screenshots and a decoded
end frame for color comparison. The report includes end-frame MAE, not a universal quality gate.
Keep that directory out of the offline bundle. A browser/runtime failure should be
reported or retried with the sampled method, not treated as a successful video.

## Exact-time sampled export for dense SVG

```text
node scripts/render_video.cjs --html deliverables/illustration-demo.html --out deliverables/illustration-drawing.mp4 --chrome "PATH_TO_CHROME" --speed 2 --view studio --width 1440 --height 900 --capture-fps 12 --fps 30 --segment 8 --hold 2
```

The helper pauses playback, sets each sample's exact drawing time, captures the browser,
and pipes PNG screenshots to FFmpeg with the same explicit color conversion. It opens a fresh browser for each segment and retries a
failed capture once. Persistent failures stop the export and preserve completed segments.
It closes only browsers/encoders owned by that job; never kill unrelated Chrome processes.

The cache key includes HTML, local comparison-image contents, view, speed and encoding
options. It will not resume stale segments after the reference or player changes. A
matching duration by itself is insufficient evidence that a segment belongs to the job.

`capture-fps` is the distinct sample cadence. `fps` is the encoded cadence and can repeat
frames. High path counts may make deterministic sampling substantially slower than video
duration. Smoke-test the helper on a short generated demo before a costly full export.

## Validation and placement

Both helpers check the MP4 with ffprobe and decode the full video with FFmpeg. Also inspect
beginning, middle and end frames: UI panels should stay synchronized, the frame should
not crop the artwork, and the end should display the complete selected reconstruction.

```text
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of json deliverables/illustration-drawing.mp4
ffmpeg -v error -i deliverables/illustration-drawing.mp4 -f null -
ffmpeg -v error -ss 12 -i deliverables/illustration-drawing.mp4 -frames:v 1 build/video-middle.png
```

Save the video in the user's requested workspace/output directory. If a ZIP is requested,
include completed MP4, demo, standalone SVG/HTML and the local reference only when
comparison was requested. The SVG player must not depend on the MP4 or external tools.
