// Voice-over: one Kokoro clip per sentence of vo/plan.json (local TTS through `hyperframes tts`), cached by text,
// voice and speed, plus vo/timing.json with every clip's duration for tools/build.mjs.
// Needs HYPERFRAMES_PYTHON pointing at video/tts/.venv (Poetry env with kokoro-onnx).
// Usage: node tools/vo.mjs
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const root = new URL("..", import.meta.url);
const path = (p) => new URL(p, root).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const plan = JSON.parse(readFileSync(path("vo/plan.json"), "utf8"));
mkdirSync(path("audio/vo"), { recursive: true });
process.env.HYPERFRAMES_PYTHON ??= path("tts/.venv/Scripts/python.exe");
process.env.DO_NOT_TRACK = "1";

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const duration = (file) =>
  Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]).toString().trim());

const timing = { voice: plan.voice, speed: plan.speed, scenes: [] };
for (const scene of plan.scenes) {
  const clips = [];
  for (const [i, text] of scene.sentences.entries()) {
    const key = createHash("sha1").update(`${plan.voice}|${plan.speed}|${text}`).digest("hex").slice(0, 10);
    const file = `audio/vo/${scene.id}-${i}-${key}.wav`;
    if (!existsSync(path(file))) {
      // the text goes through a file: Windows runs npx through a shell, which would split it on spaces
      const txt = path(`audio/vo/${scene.id}-${i}-${key}.txt`);
      writeFileSync(txt, text);
      execFileSync(npx, ["-y", "hyperframes@0.8.124", "tts", txt, "-v", plan.voice, "-s", String(plan.speed), "-o", path(file)], {
        stdio: "ignore",
        shell: process.platform === "win32",
      });
    }
    clips.push({ text, file, dur: +duration(path(file)).toFixed(3) });
    console.log(`${scene.id}#${i} ${clips.at(-1).dur}s  ${text}`);
  }
  timing.scenes.push({ ...scene, sentences: undefined, clips });
}
writeFileSync(path("vo/timing.json"), JSON.stringify(timing, null, 2));
const total = timing.scenes.reduce((s, sc) => s + sc.clips.reduce((a, c) => a + c.dur, 0), 0);
console.log(`speech total ${total.toFixed(1)}s`);
