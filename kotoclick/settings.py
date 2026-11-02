"""App settings. Stored in settings.json in the user's folder."""
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .paths import env, legacy_settings_file, settings_file

BUTTONS = ("left", "right", "middle")
# all app hotkeys (settings field -> default key)
HOTKEY_DEFAULTS = {
    "hotkey_click": "f6",
    "hotkey_record": "f7",
    "hotkey_play": "f8",
    "hotkey_panic": "f9",
    "hotkey_stop": "esc",     # second "stop" key; "" = disabled (then Esc can be recorded into a macro)
}


@dataclass
class Settings:
    # Hotkeys (names in hotkeys.key_to_name format)
    hotkey_click: str = "f6"
    hotkey_record: str = "f7"
    hotkey_play: str = "f8"
    hotkey_panic: str = "f9"
    hotkey_stop: str = "esc"      # extra "stop" key, can be changed or removed ("")

    # Simple mode
    interval_value: float = 100.0   # number from the "interval" field
    interval_unit: str = "ms"       # "ms" or "s"
    button: str = "left"            # left / right / middle
    double_click: bool = False
    repeat_forever: bool = True
    repeat_count: int = 100

    # Macros
    record_moves: bool = False
    macro_loop: bool = True
    macro_repeat_count: int = 3
    last_macro: str = ""

    # Window
    current_tab: int = 0
    always_on_top: bool = False
    record_keys: bool = False   # record keys into the macro (only while recording)
    language: str = ""          # "ru" / "en"; "" = not chosen yet: on first run use the system language

    # Macro library (files in the macros/ folder)
    current_macro: str = ""         # file name of the current macro
    library_migrated: bool = False  # old macros already migrated into the library

    # The cat
    anim_enabled: bool = True       # all cat animations (master switch: hat, disco, fades...)
    anim_hat: bool = True           # the headset hat bounces on every click
    anim_disco: bool = True         # "vibe disco" on very fast clicking
    chatty: bool = True             # "Chatty cat": cute phrases in the bubble (phrases.py)

    # Sounds
    sound_volume: int = 70          # 0..100
    sound_countdown: bool = True    # countdown sound (one file, played once at the start of the 3 s countdown)
    sound_record_start: bool = True  # "meow": recording started
    sound_record_stop: bool = True  # recording finished
    sound_play_start: bool = True   # macro started
    sound_tick: bool = True         # quiet ticks while recording
    sound_custom: dict = field(default_factory=dict)  # event -> path to a custom sound file
    countdown_record: bool = True   # 3 seconds before recording starts
    countdown_play: bool = False    # 3 seconds before a macro started by hotkey too

    # Telegram bot bubble
    promo_enabled: bool = True

    @property
    def interval_seconds(self) -> float:
        value = self.interval_value / 1000.0 if self.interval_unit == "ms" else self.interval_value
        return max(0.001, value)

    def validate(self) -> "Settings":
        """Clamps values to valid ones (in case the file was edited by hand)."""
        if self.interval_unit not in ("ms", "s"):
            self.interval_unit = "ms"
        if self.button not in BUTTONS:
            self.button = "left"
        try:
            self.interval_value = float(self.interval_value)
        except (TypeError, ValueError):
            self.interval_value = 100.0
        min_value = 1.0 if self.interval_unit == "ms" else 0.001
        self.interval_value = max(min_value, min(self.interval_value, 3_600_000.0))
        self.repeat_count = max(1, int(self.repeat_count))
        self.macro_repeat_count = max(1, int(self.macro_repeat_count))
        self.current_tab = 0 if self.current_tab not in (0, 1, 2) else self.current_tab
        try:
            self.sound_volume = max(0, min(100, int(self.sound_volume)))
        except (TypeError, ValueError):
            self.sound_volume = 70
        if not isinstance(self.sound_custom, dict):
            self.sound_custom = {}
        # only known events and only string paths (same as sounds.EVENTS)
        known = ("countdown", "record_start", "record_stop", "play_start", "tick")
        self.sound_custom = {k: v for k, v in self.sound_custom.items() if k in known and isinstance(v, str) and v}
        if not isinstance(self.current_macro, str):
            self.current_macro = ""
        for f in fields(self):
            if f.type in (bool, "bool"):
                setattr(self, f.name, bool(getattr(self, f.name)))
        if self.language not in ("ru", "en", ""):
            self.language = ""          # unknown value: detect from the system
        for f, default in HOTKEY_DEFAULTS.items():
            value = getattr(self, f)
            if not isinstance(value, str) or (not value and f != "hotkey_stop"):
                setattr(self, f, default)
        used = [getattr(self, f) for f in HOTKEY_DEFAULTS if getattr(self, f)]
        if len(used) != len(set(used)):      # one key for two actions: restore the defaults
            for f, default in HOTKEY_DEFAULTS.items():
                setattr(self, f, default)
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in (data or {}).items() if k in known}
        try:
            return cls(**clean).validate()
        except (TypeError, ValueError):
            return cls()

    # --- file ---
    @classmethod
    def load(cls, path: Path = None) -> "Settings":
        if path:
            path = Path(path)
        else:
            path = settings_file()
            # after the Kotoklik -> KotoClick rename: no new settings.json yet, so read the old one
            # (the next save() writes to the new folder; the old file is left as it is)
            if not path.exists() and not env("CONFIG_DIR") and legacy_settings_file().is_file():
                path = legacy_settings_file()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return cls.from_dict(json.load(fh))
        except (OSError, ValueError):
            return cls()

    def save(self, path: Path = None) -> None:
        path = Path(path) if path else settings_file()
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
        tmp.replace(path)  # atomic replace: the file will not get corrupted on a crash
