"""Global hotkeys.

How it works: pynput installs a system keyboard hook so that F6 and the other keys
work even when the KotoClick window is minimised.
For peace of mind: this listener does NOT record or send keystrokes anywhere.
Each press is only compared with the list of assigned keys, and a signal reaches
the app only on a match (or in "press a key" capture mode).
(Recording keys into a macro is a separate feature in engine.py: it works only
while recording is on and the "Record keystrokes" switch is enabled.)

pynput callbacks run in a separate thread, so events reach the UI only through
a Qt signal (which delivers them to the main thread by itself).
"""
import sys
import threading
import time

REPEAT_WINDOW = 1.1  # sec; Windows auto-repeat starts after at most 1 s
DEBOUNCE = 0.15      # sec; "bounce": a duplicate event from a single press

from PySide6.QtCore import QObject, Signal

from .i18n import tr

# Nice labels for keys (same in both languages, except Space)
_PRETTY = {
    "esc": "Esc", "enter": "Enter", "tab": "Tab",
    "backspace": "Backspace", "delete": "Delete", "insert": "Insert",
    "home": "Home", "end": "End", "page_up": "PgUp", "page_down": "PgDn",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "caps_lock": "CapsLock", "pause": "Pause", "scroll_lock": "ScrollLock",
    "print_screen": "PrtSc", "num_lock": "NumLock", "menu": "Menu",
    "shift": "Shift", "shift_l": "Shift", "ctrl": "Ctrl", "ctrl_l": "Ctrl",
    "alt": "Alt", "alt_l": "Alt", "alt_gr": "AltGr", "cmd": "Win", "cmd_l": "Win",
}
# Right-hand modifiers: label + a localized "(R)" suffix
_RIGHT = {"shift_r": "Shift", "ctrl_r": "Ctrl", "alt_r": "Alt", "cmd_r": "Win"}


def vk_name(vk) -> str:
    """Key name from its virtual key code (on Windows: letters, digits, numpad digits)."""
    if vk is None:
        return ""
    if sys.platform.startswith("win"):
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x60 <= vk <= 0x69:
            return f"num{vk - 0x60}"
    elif 0x20 < vk < 0x7F:  # X11: codes of printable characters match ASCII
        return chr(vk).lower()
    return f"vk{vk}"


def key_to_name(key) -> str:
    """Turns a pynput key into a short name: 'f6', 'esc', 'a', 'num5'...
    On Windows letters are taken from the key code, so a Russian layout does not interfere."""
    name = getattr(key, "name", None)  # special keys (Key.f6) have a name
    if name:
        return name
    char = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    if char and char.isascii() and char.isalnum():
        return char.lower()
    if vk is not None and sys.platform.startswith("win"):
        return vk_name(vk)
    if char and char.isprintable():
        return char.lower()
    if vk is not None:
        return f"vk{vk}"
    return ""


def pretty_key(name: str) -> str:
    if not name:
        return "—"
    if name == "space":
        return tr("k_space")
    if name in _PRETTY:
        return _PRETTY[name]
    if name in _RIGHT:
        return _RIGHT[name] + tr("k_right_suffix")
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    if name.startswith("num") and name[3:].isdigit():
        return "Num " + name[3:]
    if name.startswith("vk") and name[2:].isdigit():
        return "#" + name[2:]
    return name.upper() if len(name) == 1 else name.replace("_", " ").title()


class HotkeyListener(QObject):
    """Listens to the keyboard and reports presses of assigned keys."""

    hotkeyPressed = Signal(str)   # name of the assigned key
    keyCaptured = Signal(str)     # any key in "press a key" mode
    failed = Signal(str)          # failed to start (message for the user)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._watched = set()
        self._capturing = False
        # A held key sends "presses" again and again (auto-repeat): skip them.
        # We keep the time of the last press: if a release ever gets lost,
        # the key "comes back to life" by itself after about a second.
        self._held = {}
        self._last_fire = {}       # when the key last fired
        self._listener = None

    # --- control from the main thread ---
    def set_watched(self, names):
        with self._lock:
            self._watched = {n for n in names if n}

    def begin_capture(self):
        with self._lock:
            self._capturing = True

    def cancel_capture(self):
        with self._lock:
            self._capturing = False

    def start(self) -> bool:
        try:
            from pynput import keyboard  # import here: without a display (tests) pynput may fail to load
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
            return True
        except Exception as exc:  # noqa: BLE001 - show the reason to the user
            self.failed.emit(tr("err_hotkeys", err=exc))
            return False

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    # --- called from the pynput thread ---
    def _on_press(self, key):
        name = key_to_name(key)
        if not name:
            return
        now = time.monotonic()
        with self._lock:
            last = self._held.get(name)
            self._held[name] = now
            if last is not None and now - last < REPEAT_WINDOW:
                return  # this is auto-repeat of a held key
            if now - self._last_fire.get(name, -10.0) < DEBOUNCE:
                return  # one press arrived twice
            self._last_fire[name] = now
            capturing = self._capturing
            if capturing:
                self._capturing = False
            watched = name in self._watched
        if capturing:
            self.keyCaptured.emit(name)
        elif watched:
            self.hotkeyPressed.emit(name)

    def _on_release(self, key):
        name = key_to_name(key)
        with self._lock:
            self._held.pop(name, None)
