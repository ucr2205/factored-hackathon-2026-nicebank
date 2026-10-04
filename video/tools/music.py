"""Original background score for the video, synthesized from code (no samples, no licences).

Reads vo/scenes.json (written by tools/build.mjs) so every musical section lines up with a scene: a dark pulse under
the problem, a riser and a hit on "Meet NiceBank", an uplifting groove under the product, a build into the results
and a resolved chord on the close. Writes audio/music.wav (44.1 kHz stereo).

Usage (from video/): poetry -C tts run python tools/music.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 44100
BPM = 100
BEAT = 60 / BPM
rng = np.random.default_rng(7)  # fixed seed: the same score on every run


def note(name: str) -> float:
    """Frequency of a note name like 'A3' or 'C#4'."""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def lowpass(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def highpass(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def env(n: int, attack: float, release: float) -> np.ndarray:
    """Attack/release envelope over n samples (seconds)."""
    e = np.ones(n)
    a, r = min(n, int(attack * SR)), min(n, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def saw(freq: float, n: int, detune: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    phase = (freq * (1 + detune) * t + rng.random()) % 1.0
    return 2 * phase - 1


def pad(chord: list[str], dur: float, cutoff: float = 1400) -> np.ndarray:
    """Warm detuned-saw pad for a chord, stereo."""
    n = int(dur * SR)
    left, right = np.zeros(n), np.zeros(n)
    for name in chord:
        f = note(name)
        for d in (-0.006, 0.0, 0.006):
            v = saw(f, n, d)
            left += v * (0.6 if d < 0 else 0.4)
            right += v * (0.6 if d > 0 else 0.4)
    e = env(n, min(1.2, dur / 3), min(1.0, dur / 3))
    return np.stack([lowpass(left, cutoff) * e, lowpass(right, cutoff) * e]) / (len(chord) * 3)


def pluck(freq: float, dur: float = 0.5) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * freq * k * t) / k**1.6 for k in range(1, 6))
    return tone * np.exp(-t * 7) * env(n, 0.004, 0.05)


def kick(dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 45 + 85 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(dur: float = 0.08) -> np.ndarray:
    n = int(dur * SR)
    return highpass(rng.standard_normal(n), 7000) * np.exp(-np.arange(n) / SR * 60) * 0.35


def boom(dur: float = 3.5) -> np.ndarray:
    """Cinematic hit: sub drop plus a noise burst."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(30 + 50 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.4)
    noise = lowpass(rng.standard_normal(n), 2500) * np.exp(-t * 5) * 0.4
    return sub + noise


def riser(dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    steps = 24  # a filter that opens step by step
    for i in range(steps):
        a, b = i * n // steps, (i + 1) * n // steps
        out[a:b] = lowpass(noise[a:b], 300 + 9000 * (i / steps) ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * (t / dur) ** 2) / SR) * 0.25
    return (out * 0.5 + tone) * (t / dur) ** 2


def reverb(x: np.ndarray, seconds: float = 2.6, mix: float = 0.28) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t * 3.2)
        ir = lowpass(ir, 5000) / np.sqrt(np.sum(ir**2))
        wet = fftconvolve(x[ch], ir)[: x.shape[1]]
        out.append(x[ch] * (1 - mix) + wet * mix)
    return np.stack(out)


def add(buf: np.ndarray, sig: np.ndarray, at: float, gain: float = 1.0, pan: float = 0.0) -> None:
    """Mix a mono or stereo signal into buf at `at` seconds."""
    i = int(at * SR)
    if i >= buf.shape[1]:
        return
    if sig.ndim == 1:
        sig = np.stack([sig * (1 - max(0, pan)), sig * (1 + min(0, pan))])
    j = min(buf.shape[1], i + sig.shape[1])
    buf[:, i:j] += sig[:, : j - i] * gain


def main() -> None:
    plan = json.loads((ROOT / "vo" / "scenes.json").read_text(encoding="utf-8"))
    total = plan["total"] + 1.5
    sc = {s["id"]: s for s in plan["scenes"]}
    start = lambda sid: sc[sid]["start"]  # noqa: E731
    end = lambda sid: sc[sid]["start"] + sc[sid]["dur"]  # noqa: E731

    pads = np.zeros((2, int(total * SR)))
    drums = np.zeros_like(pads)
    lead = np.zeros_like(pads)
    fx = np.zeros_like(pads)

    # 1. The problem: a low A minor drone with a soft heartbeat.
    add(pads, pad(["A2", "E3", "C4"], end("why") + 0.5, cutoff=700), 0, 0.9)
    t = 0.6
    while t < end("why") - 0.6:
        add(drums, kick(0.35), t, 0.26)
        add(drums, kick(0.35), t + 0.28, 0.14)
        t += 1.2

    # 2. Title: riser into the hit on "Meet NiceBank".
    hit = start("title") + sc["title"]["cues"][1]
    add(fx, riser(3.2), hit - 3.2, 0.55)
    add(fx, boom(), hit, 0.9)
    add(pads, pad(["F2", "C3", "A3", "E4"], 4.2, cutoff=2600), hit, 0.75)

    # 3. The product (dispute → supervisor): uplifting groove, Am – F – C – G, one chord per bar.
    prog = [["A2", "E3", "A3", "C4"], ["F2", "C3", "F3", "A3"], ["C3", "G3", "C4", "E4"], ["G2", "D3", "G3", "B3"]]
    arps = [["A3", "C4", "E4", "A4"], ["F3", "A3", "C4", "F4"], ["C4", "E4", "G4", "C5"], ["G3", "B3", "D4", "G4"]]
    groove_from, groove_to = start("dispute"), end("supervisor")
    bar = 4 * BEAT
    b, t = 0, groove_from
    while t < groove_to:
        add(pads, pad(prog[b % 4], bar + 0.4, cutoff=1800), t, 0.6)
        for k in range(8):
            add(lead, pluck(note(arps[b % 4][k % 4]) * (2 if k >= 4 else 1), 0.45), t + k * BEAT / 2, 0.16, pan=0.3 if k % 2 else -0.3)
        for k in range(4):
            add(drums, kick(), t + k * BEAT, 0.32 if k in (0, 2) else 0.0)
            add(drums, hat(), t + k * BEAT + BEAT / 2, 0.5)
        t += bar
        b += 1

    # 4. How: the same progression, a little more drive (16th hats, bass pulse).
    t, b = start("how"), 0
    while t < end("how"):
        add(pads, pad(prog[b % 4], bar + 0.4, cutoff=2200), t, 0.55)
        for k in range(8):
            add(lead, pluck(note(prog[b % 4][0]) / 2, 0.3), t + k * BEAT / 2, 0.22)
            add(drums, hat(0.05), t + k * BEAT / 2 + BEAT / 4, 0.35)
        for k in range(4):
            add(drums, kick(), t + k * BEAT, 0.45)
        t += bar
        b += 1

    # 5. Results: build, then a bright lift on the first number.
    lift = start("results") + sc["results"]["cues"][0] + 3.0
    add(fx, riser(2.6), lift - 2.6, 0.4)
    add(fx, boom(2.5), lift, 0.55)
    t, b = start("results"), 0
    while t < end("results"):
        add(pads, pad(prog[(b + 1) % 4], bar + 0.4, cutoff=3200), t, 0.55)
        for k in range(8):
            add(lead, pluck(note(arps[(b + 1) % 4][k % 4]) * 2, 0.4), t + k * BEAT / 2, 0.18, pan=0.35 if k % 2 else -0.35)
        for k in range(4):
            add(drums, kick(), t + k * BEAT, 0.45)
            add(drums, hat(), t + k * BEAT + BEAT / 2, 0.5)
        t += bar
        b += 1

    # 6. Close: one resolved chord, held into silence.
    add(fx, boom(3.0), start("close") + 0.3, 0.5)
    add(pads, pad(["C3", "G3", "C4", "E4", "G4"], end("close") - start("close") + 1.0, cutoff=2400), start("close"), 0.8)

    mix = reverb(pads, 3.0, 0.35) + reverb(lead, 2.2, 0.3) + drums * 0.9 + reverb(fx, 2.5, 0.25)
    mix = highpass(mix, 30)
    mix /= np.max(np.abs(mix)) / 0.89  # -1 dBFS peak
    fade = int(2.5 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade)
    out = ROOT / "audio" / "music.wav"
    sf.write(out, mix.T.astype(np.float32), SR)
    print(f"wrote {out} ({mix.shape[1] / SR:.1f} s)")


if __name__ == "__main__":
    main()
