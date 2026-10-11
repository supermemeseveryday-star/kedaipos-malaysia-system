# Kedai POS introduction video

An ~90 second introduction video with a **Chinese voiceover** and **bilingual (Chinese + English) subtitles**. It is built entirely with open-source tools that run offline:

| Part | Tool |
|---|---|
| Chinese voiceover (voice `zf_xiaobei`) | [HyperFrames](https://hyperframes.heygen.com) `tts` (local Kokoro-82M model) |
| Opening and closing animations | HyperFrames compositions (HTML + GSAP): `hyperframes/compositions/` |
| Product walkthrough, subtitles, final mix | [Remotion](https://www.remotion.dev): `remotion/src/` |

The walkthrough uses the app screenshots in [`docs/screenshots/`](../docs/screenshots/).

## Edit the script

All narration and subtitles live in [`script.json`](script.json). Each scene has a list of lines; each line has the Chinese narration (`zh`) and its English subtitle (`en`). Scene lengths and subtitle timings are calculated from the generated voice, so you can rewrite lines freely and re-run the steps below.

## Build the video

Requirements: Node.js 20+, Python 3.10+, ffmpeg/ffprobe.

```bash
cd video
pip install kokoro-onnx soundfile          # local TTS engine used by `hyperframes tts`
(cd hyperframes && npm install)
(cd remotion && npm install)

node make-voice.mjs                        # 1. Chinese voiceover → remotion/public/voice/, timings → remotion/src/timeline.json
(cd hyperframes && npx hyperframes browser ensure && node render.mjs)   # 2. intro/outro → remotion/public/hf/
(cd remotion && npm run render)            # 3. final video → remotion/out/kedai-pos-intro.mp4
```

- `node make-voice.mjs --force` regenerates every voice line; otherwise only missing lines are generated.
- `cd remotion && npm run studio` opens Remotion Studio to preview and scrub the video.
- To reuse HyperFrames' Chrome for Remotion, set `REMOTION_BROWSER` to the path printed by `npx hyperframes browser path`.

Generated media (voice WAVs, intro/outro MP4s, copied screenshots, the final video) is not committed. Rebuild it with the steps above.
