"""Trimming a custom sound: read into PCM, cut a piece, smooth edges, write a WAV.

No new libraries and no external programs:
  * WAV is read with the standard wave module;
  * MP3 / OGG / M4A / FLAC are decoded by QtMultimedia (QAudioDecoder, the same Qt that draws the window);
  * the result is written with the wave module: 16 bit, sample rate and channels as in the source.
"""
from __future__ import annotations

import array
import math
import re
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

FADE_MS = 10            # smooth start and end so it does not click
DECODE_TIMEOUT_MS = 20000
MAX_DECODE_SECONDS = 600   # do not read beyond 10 minutes: an event sound never needs that much


class TrimError(Exception):
    """The sound could not be read or saved (the text is for the user)."""


@dataclass
class Pcm:
    samples: array.array      # 16-bit samples, channels interleaved (L R L R ...)
    channels: int
    rate: int

    @property
    def frames(self) -> int:
        return len(self.samples) // max(1, self.channels)

    @property
    def duration(self) -> float:
        return self.frames / self.rate if self.rate else 0.0

    def to_bytes(self) -> bytes:
        a = array.array("h", self.samples)
        if sys.byteorder == "big":
            a.byteswap()
        return a.tobytes()


def _clip16(v: float) -> int:
    return max(-32768, min(32767, int(v)))


def _from_raw(raw: bytes, width: int, kind: str = "int") -> array.array:
    """PCM bytes (little-endian) -> array('h')."""
    if kind == "float":
        a = array.array("f")
        a.frombytes(raw[: len(raw) // 4 * 4])
        if sys.byteorder == "big":
            a.byteswap()
        return array.array("h", (_clip16(v * 32767) for v in a))
    if width == 2:
        a = array.array("h")
        a.frombytes(raw[: len(raw) // 2 * 2])
        if sys.byteorder == "big":
            a.byteswap()
        return a
    if width == 1:                         # 8-bit unsigned, silence = 128
        return array.array("h", ((b - 128) << 8 for b in raw))
    if width in (3, 4):                    # 24/32 bit: take the two most significant bytes
        n = len(raw) // width
        return array.array("h", (int.from_bytes(raw[i * width + width - 2: i * width + width], "little", signed=True)
                                 for i in range(n)))
    raise TrimError(f"{width * 8}-bit WAV")


def read_wav(path: str) -> Pcm:
    try:
        with wave.open(str(path), "rb") as w:
            p = w.getparams()
            raw = w.readframes(p.nframes)
    except (OSError, wave.Error, EOFError) as exc:
        raise TrimError(str(exc) or "bad WAV") from exc
    if not raw:
        raise TrimError("empty file")
    return Pcm(_from_raw(raw, p.sampwidth), p.nchannels, p.framerate)


def decode_with_qt(path: str, timeout_ms: int = DECODE_TIMEOUT_MS) -> Pcm:
    """MP3/OGG/M4A -> PCM via QAudioDecoder (needs a running QApplication)."""
    try:
        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat
    except ImportError as exc:
        raise TrimError("QtMultimedia") from exc
    dec = QAudioDecoder()
    want = QAudioFormat()
    want.setSampleFormat(QAudioFormat.Int16)     # a request; the decoder may still return float, which is handled
    dec.setAudioFormat(want)
    dec.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
    out = array.array("h")
    state = {"rate": 0, "channels": 0, "error": "", "done": False}
    loop = QEventLoop()

    def on_ready():
        buf = dec.read()
        if not buf.isValid():
            return
        fmt = buf.format()
        sf = fmt.sampleFormat()
        raw = bytes(buf.constData())
        if sf == QAudioFormat.Float:
            out.extend(_from_raw(raw, 4, "float"))
        elif sf == QAudioFormat.Int16:
            out.extend(_from_raw(raw, 2))
        elif sf == QAudioFormat.Int32:
            out.extend(_from_raw(raw, 4))
        elif sf == QAudioFormat.UInt8:
            out.extend(_from_raw(raw, 1))
        else:
            state["error"] = "unknown sample format"
        state["rate"], state["channels"] = fmt.sampleRate(), fmt.channelCount()
        if len(out) >= state["rate"] * state["channels"] * MAX_DECODE_SECONDS:
            state["done"] = True
            dec.stop()
            loop.quit()

    def on_error(*_):
        state["error"] = dec.errorString() or "decode error"
        loop.quit()

    def on_finished():
        state["done"] = True
        loop.quit()

    dec.bufferReady.connect(on_ready)
    dec.finished.connect(on_finished)
    dec.error.connect(on_error)
    QTimer.singleShot(timeout_ms, loop.quit)
    dec.start()
    if not state["done"] and not state["error"]:
        loop.exec()
    dec.stop()
    if state["error"]:
        raise TrimError(state["error"])
    if not out or not state["rate"] or not state["channels"]:
        raise TrimError("no audio" if state["done"] else "timeout")
    return Pcm(out, state["channels"], state["rate"])


def load_pcm(path: str) -> Pcm:
    """Read any supported sound fully into PCM."""
    if not Path(path).is_file():
        raise TrimError("file not found")
    if Path(path).suffix.lower() in (".wav", ".wave"):
        try:
            return read_wav(path)
        except TrimError:
            pass            # a "WAV" may turn out to be compressed: try via Qt
    return decode_with_qt(path)


def trim(pcm: Pcm, start: float, end: float, fade_ms: int = FADE_MS) -> Pcm:
    """Cut [start, end) seconds and add short smooth edges."""
    ch = max(1, pcm.channels)
    a = max(0, min(pcm.frames, int(round(start * pcm.rate))))
    b = max(a, min(pcm.frames, int(round(end * pcm.rate))))
    part = array.array("h", pcm.samples[a * ch: b * ch])
    frames = b - a
    fade = min(int(pcm.rate * fade_ms / 1000), frames // 2)
    for i in range(fade):
        k = i / fade
        for c in range(ch):
            part[i * ch + c] = int(part[i * ch + c] * k)              # start: fade in from silence
            j = (frames - 1 - i) * ch + c
            part[j] = int(part[j] * k)                                # end: fade out to silence
    return Pcm(part, pcm.channels, pcm.rate)


def write_wav(pcm: Pcm, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(pcm.channels)
            w.setsampwidth(2)
            w.setframerate(pcm.rate)
            w.writeframes(pcm.to_bytes())
        tmp.replace(path)
    except OSError as exc:
        raise TrimError(str(exc)) from exc
    return path


def safe_name(event: str, source: str) -> str:
    """File name for a trimmed sound: countdown_my-song.wav (without characters forbidden on Windows)."""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(source).stem).strip(" .")[:60] or "sound"
    return f"{event}_{stem}.wav"


def save_trimmed(pcm: Pcm, start: float, end: float, folder, event: str, source: str) -> Path:
    """Save the piece [start, end) into folder and return the path to the new WAV."""
    if end - start < 0.05:
        raise TrimError("too short")
    return write_wav(trim(pcm, start, end), Path(folder) / safe_name(event, source))


def peaks(pcm: Pcm, bins: int) -> list:
    """Envelope for the picture: max |amplitude| (0..1) in each of `bins` segments."""
    if bins <= 0 or pcm.frames == 0:
        return []
    ch = max(1, pcm.channels)
    step = pcm.frames / bins
    out = []
    s = pcm.samples
    for i in range(bins):
        a = int(i * step) * ch
        b = max(a + ch, int((i + 1) * step) * ch)
        chunk = s[a:b]
        stride = max(1, len(chunk) // 400)     # for long files do not look at every sample
        m = max((abs(v) for v in chunk[::stride]), default=0)
        out.append(math.sqrt(m / 32768.0))      # square root: quiet parts are visible too
    return out
