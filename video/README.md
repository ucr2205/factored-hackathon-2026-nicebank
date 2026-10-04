# NiceBank video pitch (HyperFrames)

The ≤ 3 minute submission video: a launch-style trailer built with [HyperFrames](https://github.com/heygen-com/hyperframes)
(HTML + GSAP rendered to MP4). English voice-over, real footage of the app in Spanish and Portuguese with English
translation chips, and an original score synthesized from code.

| Path | What |
|---|---|
| `SCRIPT.md` | Script and storyboard (approved by the team lead) |
| `vo/plan.json` | Voice-over sentences per scene, voice (`af_sky`), speed, gaps and scene lead/tail |
| `tools/vo.mjs` | One Kokoro clip per sentence through `hyperframes tts` (local, nothing leaves the machine) → `audio/vo/`, `vo/timing.json` |
| `tools/record.mjs` | Playwright recorder for the real app at `http://localhost:8088`; the operator types every login and 2FA code → `clips/<scene>.webm`, `.marks.json`, 2x screenshots |
| `tools/build.mjs` | Timeline: footage scenes (`compositions/<scene>.html`) and `index.html` from the voice-over timing and the clip marks |
| `tools/music.py` | Original score (numpy/scipy synthesis) aligned to the scenes → `audio/music.wav` |
| `compositions/*.html` | Motion scenes written by hand: `why`, `title`, `how`, `results`, `close` |
| `assets/` | Local fonts (Montserrat, Inter), GSAP, logo, `brand.css` |

`clips/`, `audio/`, `renders/` and `snapshots/` are git-ignored.

## Rebuild

```bash
cd video
npm install
cd tts && poetry install && cd ..                       # Kokoro + numpy/scipy (Poetry env for the Python bits)
HYPERFRAMES_PYTHON=tts/.venv/Scripts/python.exe node tools/vo.mjs
node tools/record.mjs                                    # needs the local stack (Mailpit SMTP) and a person for logins
for n in dispute explain portuguese stolen agent supervisor; do
  ffmpeg -y -i clips/$n.webm -vf "crop=1440:810:0:0,fps=30" -c:v libx264 -crf 14 -pix_fmt yuv420p -an clips/$n.mp4
done
node tools/build.mjs
poetry -C tts run python "$PWD/tools/music.py"
npx hyperframes lint && npx hyperframes render -o renders/nicebank.mp4 --quality looks --video-frame-format png
```

Figures on screen come from `eval/reports/test-v2-20261004T213856Z.md` (120 held-out cases, case set v2).
