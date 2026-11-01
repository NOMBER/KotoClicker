"""
Generator of KotoClick's default sounds (pure Python, no third-party libraries).

All sounds are synthesised right here: no foreign samples and no licences.
Output: assets/sounds/*.wav (16 bit, mono, 22050 Hz).

Run:  python tools/make_sounds.py
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def write(name, samples, peak=0.85):
    """Normalises the volume and saves a WAV."""
    m = max(1e-9, max(abs(s) for s in samples))
    k = peak / m
    data = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s * k)) * 32767)) for s in samples)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    print(f"{name}: {len(samples) / RATE:.2f} s")


def env_adsr(i, n, attack=0.005, release=0.05):
    t, dur = i / RATE, n / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = min(1.0, (dur - t) / release) if release > 0 else 1.0
    return max(0.0, min(a, r))


def tone(freq, dur, harmonics=((1, 1.0),), decay=None, attack=0.005, release=0.04):
    n = int(dur * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        v = sum(a * math.sin(2 * math.pi * freq * h * t) for h, a in harmonics)
        if decay:
            v *= math.exp(-t / decay)
        out.append(v * env_adsr(i, n, attack, release))
    return out


def silence(dur):
    return [0.0] * int(dur * RATE)


def beep():
    # "beep": a short clean tone, like a timer
    return tone(1046.5, 0.13, ((1, 1.0), (2, 0.12)), attack=0.004, release=0.03)


def countdown(total=3.0):
    """One file for the whole countdown: a "beep" at 0, 1 and 2 seconds, silence in between, 3 s in total.
    Played once at the start of the countdown; the "meow" / start sound plays right after it."""
    out = silence(total)
    b = beep()
    for sec in (0, 1, 2):
        start = int(sec * RATE)
        for i, v in enumerate(b):
            out[start + i] += v
    return out


def tick():
    # a quiet "tick": a very short wooden click
    rnd = random.Random(3)
    n = int(0.035 * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        v = 0.7 * math.sin(2 * math.pi * 1900 * t) + 0.3 * (rnd.random() * 2 - 1)
        out.append(v * math.exp(-t / 0.006) * env_adsr(i, n, 0.0008, 0.004))
    return out


def chime(freqs, step, note_dur, decay):
    """A few "bell" notes in a row (a marimba-like timbre)."""
    total = int((step * (len(freqs) - 1) + note_dur) * RATE)
    out = [0.0] * total
    for k, f in enumerate(freqs):
        start = int(k * step * RATE)
        note = tone(f, note_dur, ((1, 1.0), (2, 0.25), (3, 0.08)), decay=decay, attack=0.003, release=0.05)
        for i, v in enumerate(note):
            if start + i < total:
                out[start + i] += v
    return out


def play_start():
    # "let's go!": a cheerful C-E-G-C rise
    return chime([523.25, 659.25, 783.99, 1046.5], 0.07, 0.32, 0.12)


def record_stop():
    # "done": two notes down, softly
    return chime([783.99, 523.25], 0.13, 0.42, 0.16)


def meow():
    """A synthetic "meow": a harmonic source with changing pitch
    and formants that "glide" from "ee" through "ah" to "oo" (mee-ah-oo)."""
    dur = 0.82
    n = int(dur * RATE)
    rnd = random.Random(11)

    def f0_at(x):  # voice pitch: up towards the middle of "ah", then down
        if x < 0.35:
            return 560 + (790 - 560) * math.sin(x / 0.35 * math.pi / 2)
        return 790 - (790 - 470) * ((x - 0.35) / 0.65) ** 1.3

    def formants_at(x):  # (frequency, width, gain) for F1, F2, F3
        def lerp(a, b, u):
            return a + (b - a) * u
        if x < 0.3:          # "ee" -> "ah"
            u = x / 0.3
            f1, f2 = lerp(420, 1000, u), lerp(2300, 1550, u)
        elif x < 0.65:       # "ah"
            u = (x - 0.3) / 0.35
            f1, f2 = lerp(1000, 950, u), lerp(1550, 1350, u)
        else:                # "ah" -> "oo"
            u = (x - 0.65) / 0.35
            f1, f2 = lerp(950, 450, u), lerp(1350, 850, u)
        return ((f1, 260, 1.0), (f2, 320, 0.55), (3000, 450, 0.18))

    phase = [0.0] * 14
    out = []
    for i in range(n):
        x = i / n
        t = i / RATE
        f0 = f0_at(x) * (1 + 0.012 * math.sin(2 * math.pi * 6.0 * t))   # slight vibrato
        fm = formants_at(x)
        v = 0.0
        for h in range(1, 15):
            fh = f0 * h
            if fh > RATE / 2 - 500:
                break
            phase[h - 1] += 2 * math.pi * fh / RATE
            amp = sum(g * math.exp(-((fh - fc) / bw) ** 2) for fc, bw, g in fm) / h ** 0.3
            v += amp * math.sin(phase[h - 1])
        v += 0.03 * (rnd.random() * 2 - 1) * math.exp(-t / 0.08)        # a "breath" at the start
        # envelope: open the mouth quickly, hold, close smoothly
        a = min(1.0, t / 0.045)
        r = min(1.0, (dur - t) / 0.28) ** 1.5
        swell = 0.75 + 0.25 * math.sin(min(1.0, x / 0.5) * math.pi / 2)
        out.append(v * a * r * swell)
    return out


def main():
    write("countdown.wav", countdown(), 0.7)
    write("tick.wav", tick(), 0.5)
    write("meow.wav", meow(), 0.85)
    write("play_start.wav", play_start(), 0.75)
    write("record_stop.wav", record_stop(), 0.75)


if __name__ == "__main__":
    main()
