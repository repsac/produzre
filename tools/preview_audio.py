"""Render a Produzre MIDI file to a quick listening preview (WAV or MP3).

Not a production synth: a small, deterministic sketch renderer so a build
can be auditioned without a DAW. Guitars and bass are Karplus-Strong
plucked strings (rhythm guitar lightly driven), the lead is an overdriven
oscillator that follows the MIDI pitch wheel (so composed bends, vibrato,
and dives are audible), drums are synthesized, and the mix gets a short
room reverb.

Requires numpy (``pip install numpy``); MP3 output also needs ffmpeg.

Usage:
    python tools/preview_audio.py SONG.mid [-o out.mp3] [--seconds 90]
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import wave
from typing import Dict, List, Tuple

import mido
import numpy as np

SR = 32000

# Channel roles in Produzre's default layout.
CH_DRUMS = 9
CH_BASS = 1
CH_LEAD = 3


def _events(mid: mido.MidiFile):
    """Yield absolute-time (seconds) messages across tracks, tempo-aware."""
    tpb = mid.ticks_per_beat
    merged = []
    for ti, trk in enumerate(mid.tracks):
        t = 0
        for msg in trk:
            t += msg.time
            merged.append((t, ti, msg))
    merged.sort(key=lambda x: (x[0], x[1]))
    tempo = 500000
    last_tick = 0
    now = 0.0
    for tick, _, msg in merged:
        now += (tick - last_tick) * tempo / 1e6 / tpb
        last_tick = tick
        if msg.type == "set_tempo":
            tempo = msg.tempo
        yield now, msg


def parse(path: str):
    mid = mido.MidiFile(path)
    notes: List[Tuple[int, int, float, float, int]] = []  # ch, pitch, start, end, vel
    bends: Dict[int, List[Tuple[float, float]]] = {}
    expr: Dict[int, List[Tuple[float, float]]] = {}
    bend_range: Dict[int, float] = {}
    rpn: Dict[int, Tuple[int, int]] = {}
    active: Dict[Tuple[int, int], Tuple[float, int]] = {}
    for t, msg in _events(mid):
        if msg.type == "note_on" and msg.velocity > 0:
            active[(msg.channel, msg.note)] = (t, msg.velocity)
        elif msg.type in ("note_off", "note_on"):
            k = (msg.channel, msg.note)
            if k in active:
                st, v = active.pop(k)
                notes.append((msg.channel, msg.note, st, t, v))
        elif msg.type == "pitchwheel":
            semis = bend_range.get(msg.channel, 2.0)
            bends.setdefault(msg.channel, []).append((t, msg.pitch / 8192.0 * semis))
        elif msg.type == "control_change":
            if msg.control == 11:
                expr.setdefault(msg.channel, []).append((t, msg.value / 127.0))
            elif msg.control in (100, 101):
                lsb, msb = rpn.get(msg.channel, (127, 127))
                rpn[msg.channel] = (msg.value, msb) if msg.control == 100 else (lsb, msg.value)
            elif msg.control == 6 and rpn.get(msg.channel) == (0, 0):
                bend_range[msg.channel] = float(msg.value)
    return notes, bends, expr


def _curve(points: List[Tuple[float, float]], t0: float, n: int, default: float) -> np.ndarray:
    """Step-held control curve sampled over [t0, t0 + n/SR)."""
    if not points:
        return np.full(n, default)
    times = np.array([p[0] for p in points])
    vals = np.array([p[1] for p in points])
    ts = t0 + np.arange(n) / SR
    idx = np.searchsorted(times, ts, side="right") - 1
    out = np.where(idx >= 0, vals[np.clip(idx, 0, len(vals) - 1)], default)
    return out


def _ks(freq: float, dur: float, rng: np.random.Generator, bright: float = 0.5,
        decay: float = 0.996) -> np.ndarray:
    """Karplus-Strong pluck, vectorized one period at a time."""
    n = int(dur * SR)
    period = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, period)
    # Pre-filter the excitation for a darker or brighter pick.
    buf = bright * buf + (1 - bright) * np.convolve(buf, np.ones(4) / 4, mode="same")
    out = np.empty(n + period)
    out[:period] = buf
    pos = period
    while pos < n + period:
        seg = out[pos - period:pos]
        nxt = decay * 0.5 * (seg + np.roll(seg, 1))
        m = min(period, n + period - pos)
        out[pos:pos + m] = nxt[:m]
        pos += m
    return out[period:period + n]


def _env(n: int, attack: float, release: float, total: int) -> np.ndarray:
    e = np.ones(n)
    a = min(n, int(attack * SR))
    if a:
        e[:a] = np.linspace(0, 1, a)
    r = min(n, int(release * SR))
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _lead(pitch: int, start: float, end: float, vel: int, bends, expr_pts) -> np.ndarray:
    dur = end - start + 0.12
    n = int(dur * SR)
    bend = _curve(bends, start, n, 0.0)
    freq = 440.0 * 2 ** ((pitch + bend - 69) / 12.0)
    phase = np.cumsum(freq) / SR
    saw = 2 * (phase % 1.0) - 1
    sq = np.sign(np.sin(2 * math.pi * phase * 0.5))
    tone = 0.75 * saw + 0.25 * sq
    tone = np.tanh(3.2 * tone)  # overdrive
    # Gentle FIR low-pass to tame the fizz.
    y = np.convolve(tone, np.ones(7) / 7.0, mode="same")
    env = _env(n, 0.006, 0.1, n)
    vol = _curve(expr_pts, start, n, 1.0)
    return y * env * vol * (vel / 127.0) * 0.32


def _drum(pitch: int, vel: int, rng: np.random.Generator) -> np.ndarray:
    g = vel / 127.0
    if pitch in (35, 36):
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        f = 45 + 110 * np.exp(-t * 30)
        return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * g * 0.9
    if pitch == 37:
        t = np.arange(int(.10 * SR)) / SR
        click = np.sin(2 * math.pi * 1250 * t) + .4 * np.sin(2 * math.pi * 1830 * t)
        return click * np.exp(-t * 65) * g * .35
    if pitch in (38, 40):
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        noise = rng.uniform(-1, 1, n)
        noise = noise - np.concatenate(([0], noise[:-1])) * 0.6
        body = np.sin(2 * math.pi * 185 * t)
        return (0.55 * noise + 0.45 * body) * np.exp(-t * 18) * g * 0.6
    if pitch == 44:
        t = np.arange(int(.09 * SR)) / SR
        noise = rng.uniform(-1, 1, len(t))
        chick = noise + np.concatenate(([0], noise[:-1])) * .4
        return chick * np.exp(-t * 45) * g * .22
    if pitch in (42, 46):
        n = int((0.35 if pitch == 46 else 0.06) * SR)
        t = np.arange(n) / SR
        noise = rng.uniform(-1, 1, n)
        hp = noise - np.concatenate(([0], noise[:-1]))
        return hp * np.exp(-t * (8 if pitch == 46 else 60)) * g * 0.22
    if pitch == 53:
        t = np.arange(int(.7 * SR)) / SR
        bell = sum(np.sin(2 * math.pi * f * t) * a for f, a in
                   ((780, .55), (1193, .3), (1711, .15)))
        return bell * np.exp(-t * 8) * g * .22
    if pitch in (49, 57, 51, 59, 52, 55):
        long = pitch in (49, 57, 52, 55)
        n = int((1.6 if long else 0.5) * SR)
        t = np.arange(n) / SR
        noise = rng.uniform(-1, 1, n)
        hp = noise - np.concatenate(([0], noise[:-1]))
        ping = np.sin(2 * math.pi * 520 * t) * 0.15
        return (hp + ping) * np.exp(-t * (2.5 if long else 7)) * g * (0.2 if long else 0.14)
    # Toms and anything else.
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    base = {41: 90, 43: 105, 45: 125, 47: 145, 48: 170, 50: 200}.get(pitch, 150)
    f = base * (1 + 0.5 * np.exp(-t * 25))
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t * 10) * g * 0.6


def render(path: str, seconds: float = 0.0) -> np.ndarray:
    notes, bends, expr = parse(path)
    if seconds > 0:
        notes = [n for n in notes if n[2] < seconds]
    end = max((n[3] for n in notes), default=1.0) + 2.0
    if seconds > 0:
        end = min(end, seconds + 2.0)
    total = int(end * SR)
    mix = np.zeros((2, total))
    rng = np.random.default_rng(7)
    pans = {CH_DRUMS: 0.5, CH_BASS: 0.5, CH_LEAD: 0.58, 2: 0.3, 4: 0.72, 5: 0.65, 0: 0.4}
    for ch, pitch, st, en, vel in sorted(notes, key=lambda x: x[2]):
        i = int(st * SR)
        if i >= total:
            continue
        if ch == CH_DRUMS:
            sig = _drum(pitch, vel, rng)
        elif ch == CH_LEAD:
            sig = _lead(pitch, st, en, vel, bends.get(ch, []), expr.get(ch, []))
        else:
            freq = 440.0 * 2 ** ((pitch - 69) / 12.0)
            dur = min(en - st + 0.15, 4.0)
            bass = ch == CH_BASS
            sig = _ks(freq, dur, rng, bright=0.25 if bass else 0.6,
                      decay=0.9985 if bass else 0.997)
            n = len(sig)
            gate = np.ones(n)
            cut = int((en - st) * SR)
            if cut < n:
                gate[cut:] = np.linspace(1, 0, n - cut)
            sig = sig * gate * (vel / 127.0)
            if not bass:
                sig = np.tanh(2.0 * sig) * 0.22
            else:
                sig = sig * 0.75
        j = min(total, i + len(sig))
        p = pans.get(ch, 0.5)
        mix[0, i:j] += sig[: j - i] * math.cos(p * math.pi / 2)
        mix[1, i:j] += sig[: j - i] * math.sin(p * math.pi / 2)
    # Room: convolve with a short decaying-noise impulse response (FFT).
    ir_n = int(1.2 * SR)
    t = np.arange(ir_n) / SR
    ir = rng.normal(0, 1, (2, ir_n)) * np.exp(-t * 4.5) * 0.08
    ir[:, 0] = 1.0
    size = 1 << int(math.ceil(math.log2(total + ir_n)))
    wet = np.fft.irfft(np.fft.rfft(mix, size) * np.fft.rfft(ir, size), size)[:, :total]
    out = wet / max(1e-9, np.max(np.abs(wet))) * 0.89
    return out


def write(audio: np.ndarray, out: str) -> str:
    wav = out if out.lower().endswith(".wav") else os.path.splitext(out)[0] + ".wav"
    pcm = (np.clip(audio.T, -1, 1) * 32767).astype("<i2")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if out.lower().endswith(".mp3"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", out],
                       check=True)
        os.remove(wav)
        return out
    return wav


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("midi")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--seconds", type=float, default=0.0, help="Render only the first N seconds.")
    args = ap.parse_args(argv)
    out = args.out or os.path.splitext(args.midi)[0] + ".preview.mp3"
    print(write(render(args.midi, args.seconds), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
