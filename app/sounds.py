"""
KotoClick sounds: the countdown, a "meow" when recording starts, an end-of-recording signal,
a macro-start signal and quiet "ticks" while recording.

How we play them:
  * Windows: the standard winsound module (part of Python, nothing to install).
    We apply the volume ourselves by scaling the WAV samples before playing.
    Playback runs in a separate background thread so the window and hotkeys never lag.
  * Other systems: QSoundEffect if the QtMultimedia module is installed, otherwise silence.
  * Custom MP3 / OGG / M4A / AAC / FLAC sounds (and "unusual" WAVs the wave module cannot read):
    QMediaPlayer + QAudioOutput from QtMultimedia (the PySide6-Addons package). Qt decodes them
    itself (FFmpeg backend, Media Foundation on Windows if needed). They are played only from the
    GUI thread; a timer stops them after MAX_SECONDS. If a file cannot be read, we tell the
    window (on_error) and play the default sound instead.
A custom sound is cut at MAX_SECONDS (the countdown at COUNTDOWN_SECONDS: it is one file for all 3 seconds,
played ONCE at the start of the countdown and never repeated; cancelling the countdown stops it via stop()).
"""
import array
import io
import os
import queue
import sys
import threading
import time
import wave
from pathlib import Path

from . import paths

EVENTS = ("countdown", "record_start", "record_stop", "play_start", "tick")
DEFAULT_FILES = {
    "countdown": "countdown.wav",   # one file: a "beep" at 0, 1 and 2 seconds, 3 s in total
    "record_start": "meow.wav",
    "record_stop": "record_stop.wav",
    "play_start": "play_start.wav",
    "tick": "tick.wav",
}
# ticks while recording: deliberately quieter than the rest
EVENT_GAIN = {"tick": 0.35}
MAX_SECONDS = 5.0
COUNTDOWN_SECONDS = 3.0
# max seconds of sound per event (longer sounds are cut)
EVENT_MAX = {"countdown": COUNTDOWN_SECONDS}


def max_seconds_for(event: str) -> float:
    return EVENT_MAX.get(event, MAX_SECONDS)
STALE_AFTER = 1.5   # a sound that waited in the queue longer than this is no longer needed
# extensions handed to QMediaPlayer (WAV too, if the wave module could not read it)
MEDIA_EXTS = (".mp3", ".ogg", ".oga", ".m4a", ".aac", ".flac")
SOUND_EXTS = (".wav",) + MEDIA_EXTS


def default_path(event: str) -> str:
    return paths.asset(f"sounds/{DEFAULT_FILES[event]}")


def scaled_wav(path: str, volume: float, max_seconds: float = MAX_SECONDS) -> bytes:
    """Reads a WAV, cuts it to max_seconds and scales the volume (0..1). Returns WAV bytes."""
    with wave.open(str(path), "rb") as w:
        params = w.getparams()
        frames = w.readframes(min(w.getnframes(), int(params.framerate * max_seconds)))
    volume = max(0.0, min(1.0, volume))
    if params.sampwidth == 2:
        a = array.array("h")
        a.frombytes(frames)
        if sys.byteorder == "big":
            a.byteswap()
        a = array.array("h", (int(v * volume) for v in a))
        if sys.byteorder == "big":
            a.byteswap()
        frames = a.tobytes()
    elif params.sampwidth == 1:   # 8 bit is unsigned, silence = 128
        frames = bytes(int(128 + (b - 128) * volume) for b in frames)
    # other formats (24/32 bit) are played without volume changes
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(params.nchannels)
        out.setsampwidth(params.sampwidth)
        out.setframerate(params.framerate)
        out.writeframes(frames)
    return buf.getvalue()


def check_wav(path: str) -> bool:
    """Can this file be played (a real WAV)?"""
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() > 0
    except (OSError, wave.Error, EOFError):
        return False


_media_ok = None


def media_supported() -> bool:
    """Is QtMultimedia (QMediaPlayer) available? Without it MP3 and others cannot be played."""
    global _media_ok
    if _media_ok is None:
        try:
            from PySide6 import QtMultimedia
            _media_ok = hasattr(QtMultimedia, "QMediaPlayer") and hasattr(QtMultimedia, "QAudioOutput")
        except ImportError:
            _media_ok = False
    return _media_ok


def needs_media(path: str) -> bool:
    """A WAV the wave module understands is played as before; everything else via QMediaPlayer."""
    return not check_wav(path)


def check_sound(path: str) -> str:
    """Can the file be chosen as a custom sound? Empty string means yes, otherwise the reason:
    "bad_format" (not a sound / unknown format) or "no_media" (no QtMultimedia).
    A broken MP3 cannot be caught here: the player catches it (the error arrives in on_error)."""
    p = Path(path)
    try:
        if not p.is_file() or p.stat().st_size == 0:
            return "bad_format"
    except OSError:
        return "bad_format"
    if check_wav(path):
        return ""
    if p.suffix.lower() not in SOUND_EXTS:
        return "bad_format"
    return "" if media_supported() else "no_media"


class NullBackend:
    name = "none"

    def play(self, path: str, volume: float, on_error=None, max_seconds: float = MAX_SECONDS):
        pass

    def stop(self):
        pass

    def stop_all(self):
        pass


class WinsoundBackend:
    """Windows: winsound in a background thread (SND_MEMORY cannot be played asynchronously)."""
    name = "winsound"

    def __init__(self):
        import winsound
        self._ws = winsound
        self._q = queue.Queue()
        self._cache = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._worker, name="kotoclick-sound", daemon=True).start()

    def _data(self, path, volume, max_seconds=MAX_SECONDS):
        try:
            key = (path, os.path.getmtime(path), round(volume, 2), max_seconds)
        except OSError:
            return None
        with self._lock:
            data = self._cache.get(key)
            if data is None:
                try:
                    data = scaled_wav(path, volume, max_seconds)
                except (OSError, wave.Error, EOFError):
                    return None
                if len(self._cache) > 32:
                    self._cache.clear()
                self._cache[key] = data
        return data

    def play(self, path, volume, max_seconds=MAX_SECONDS):
        self._q.put((time.monotonic(), path, volume, max_seconds))

    def stop(self):
        """Stop the sound (countdown cancelled): drop the queue and silence the current PlaySound."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        try:
            self._ws.PlaySound(None, 0)
        except RuntimeError:
            pass

    def _worker(self):
        flags = self._ws.SND_MEMORY | self._ws.SND_NODEFAULT
        while True:
            queued_at, path, volume, max_seconds = self._q.get()
            if time.monotonic() - queued_at > STALE_AFTER:
                continue
            data = self._data(path, volume, max_seconds)
            if data:
                try:
                    self._ws.PlaySound(data, flags)
                except RuntimeError:
                    pass


class QtBackend:
    """Not Windows: QSoundEffect from QtMultimedia (if available)."""
    name = "qt"

    def __init__(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
        self._QUrl, self._QSoundEffect = QUrl, QSoundEffect
        self._effects = {}

    def play(self, path, volume, max_seconds=MAX_SECONDS):
        # default sounds are shorter than max_seconds; long custom WAVs are not cut here (only on Windows)
        eff = self._effects.get(path)
        if eff is None:
            eff = self._QSoundEffect()
            eff.setSource(self._QUrl.fromLocalFile(str(path)))
            self._effects[path] = eff
        eff.setVolume(max(0.0, min(1.0, volume)))
        eff.play()

    def stop(self):
        for eff in self._effects.values():
            eff.stop()


class QtMediaBackend:
    """MP3 / OGG / M4A and others: QMediaPlayer + QAudioOutput. Create and call only from the GUI thread.

    One player per file (there are few: at most one per event),
    volume via QAudioOutput.setVolume (0..1), cutting via a QTimer at max_seconds."""
    name = "qtmedia"
    MAX_PLAYERS = 8

    def __init__(self, max_seconds: float = MAX_SECONDS):
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self._QTimer, self._QUrl = QTimer, QUrl
        self._QAudioOutput, self._QMediaPlayer = QAudioOutput, QMediaPlayer
        self.max_ms = int(max_seconds * 1000)
        self._slots = {}   # (path, modification time) -> _Slot

    class _Slot:
        __slots__ = ("player", "output", "timer", "on_error", "failed")

    def _slot(self, path):
        try:
            key = (path, os.path.getmtime(path))
        except OSError:
            key = (path, 0)
        slot = self._slots.get(key)
        if slot is not None:
            return slot
        if len(self._slots) >= self.MAX_PLAYERS:
            old_key = next(iter(self._slots))
            self._drop(self._slots.pop(old_key))
        slot = self._Slot()
        slot.on_error, slot.failed = None, ""
        slot.player = self._QMediaPlayer()
        slot.output = self._QAudioOutput()
        slot.player.setAudioOutput(slot.output)
        slot.timer = self._QTimer(singleShot=True, interval=self.max_ms)
        slot.timer.timeout.connect(slot.player.stop)          # cut at MAX_SECONDS
        slot.player.errorOccurred.connect(lambda _err, text, s=slot: self._failed(s, text))
        slot.player.setSource(self._QUrl.fromLocalFile(str(path)))
        self._slots[key] = slot
        return slot

    def _failed(self, slot, text):
        slot.timer.stop()
        if slot.failed:
            return
        slot.failed = text or "decode error"
        if slot.on_error:
            slot.on_error(slot.failed)

    @staticmethod
    def _drop(slot):
        slot.timer.stop()
        slot.player.stop()
        slot.player.deleteLater()
        slot.output.deleteLater()
        slot.timer.deleteLater()

    def play(self, path, volume, on_error=None, max_seconds=None):
        slot = self._slot(path)
        slot.on_error = on_error
        if slot.failed:                       # we already know the file cannot be read
            if on_error:
                on_error(slot.failed)
            return
        slot.output.setVolume(max(0.0, min(1.0, volume)))
        slot.player.stop()
        slot.player.setPosition(0)
        slot.player.play()
        slot.timer.start(int((max_seconds or self.max_ms / 1000) * 1000))

    def stop(self):
        self.stop_all()

    def stop_all(self):
        for slot in self._slots.values():
            slot.timer.stop()
            slot.player.stop()


def auto_media_backend():
    """A player for MP3 etc., or None if there is no QtMultimedia (or sound is off)."""
    if (paths.env("SOUND") or "").lower() in ("0", "off", "none"):
        return NullBackend()
    if not media_supported():
        return None
    try:
        return QtMediaBackend()
    except (ImportError, RuntimeError):
        return None


def auto_backend():
    if (paths.env("SOUND") or "").lower() in ("0", "off", "none"):
        return NullBackend()
    if sys.platform.startswith("win"):
        try:
            return WinsoundBackend()
        except ImportError:
            return NullBackend()
    try:
        return QtBackend()
    except ImportError:
        return NullBackend()


class SoundBoard:
    """Decides which file to play and how loud, based on the user's settings."""

    def __init__(self, settings, backend=None, media=None, on_error=None):
        self.settings = settings
        self.backend = backend if backend is not None else auto_backend()
        # the player for MP3 etc. is created on first use (QtMultimedia loads lazily)
        self.media = media
        self._media_ready = media is not None
        self.on_error = on_error      # on_error(event, path, reason): the window shows a message
        self.broken = {}              # path -> reason: these files do not play, the default sound is used instead

    def media_backend(self):
        if not self._media_ready:
            self._media_ready = True
            self.media = auto_media_backend()
        return self.media

    def forget(self, path: str):
        """The user picked the file again: give it another chance."""
        self.broken.pop(path, None)

    def enabled(self, event: str) -> bool:
        return bool(getattr(self.settings, f"sound_{event}", False))

    def custom(self, event: str) -> str:
        return (self.settings.sound_custom or {}).get(event, "")

    def path_for(self, event: str) -> str:
        p = self.custom(event)
        if p and p not in self.broken and Path(p).is_file():
            return p
        return default_path(event)

    def volume_for(self, event: str) -> float:
        return self.settings.sound_volume / 100.0 * EVENT_GAIN.get(event, 1.0)

    def play(self, event: str, preview: bool = False) -> bool:
        """preview=True is the play button in the settings: plays even if the event is turned off."""
        if not preview and not self.enabled(event):
            return False
        vol = self.volume_for(event)
        if vol <= 0:
            return False
        limit = max_seconds_for(event)
        path = self.path_for(event)
        if path != default_path(event) and needs_media(path):
            media = self.media_backend()
            if media is None:                       # no QtMultimedia: play the default
                self._failed(event, path, "no_media")
                path = default_path(event)
            else:
                media.play(path, vol, on_error=lambda text, e=event, p=path: self._media_failed(e, p, text),
                           max_seconds=limit)
                return True
        self.backend.play(path, vol, max_seconds=limit)
        return True

    def stop(self):
        """Silence everything that is playing now (e.g. the countdown was cancelled)."""
        stop = getattr(self.backend, "stop", None)
        if stop:
            stop()
        if self.media is not None:
            media_stop = getattr(self.media, "stop_all", None)
            if media_stop:
                media_stop()

    def _failed(self, event, path, reason):
        first = path not in self.broken
        self.broken[path] = reason
        if first and self.on_error:
            self.on_error(event, path, reason)

    def _media_failed(self, event, path, text):
        """QMediaPlayer could not read the file: report it and play the default sound right away."""
        self._failed(event, path, text or "decode error")
        self.backend.play(default_path(event), self.volume_for(event), max_seconds=max_seconds_for(event))
