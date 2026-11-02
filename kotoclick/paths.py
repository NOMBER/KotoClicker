"""File locations: the app's resources and the user's settings folder.

No registry writes, only plain JSON files:
  Windows: %APPDATA%\\KotoClick\\
  macOS:   ~/Library/Application Support/KotoClick/
  Linux:   ~/.config/KotoClick/

Older versions were called "Kotoklik" and used a folder with that name. On the first run
of this version, if the old folder exists and the new one does not, the old folder is COPIED
to the new name (the old one is never deleted). If copying fails, the old folder keeps being
used as is. Environment variables: KOTOCLICK_* (the old KOTOKLIK_* names still work).
"""
import os
import shutil
import sys
from pathlib import Path

from . import APP_NAME, LEGACY_APP_NAME


def env(name: str):
    """Value of KOTOCLICK_<name>, or of the old KOTOKLIK_<name> if the new one is not set."""
    return os.environ.get("KOTOCLICK_" + name) or os.environ.get("KOTOKLIK_" + name)


def resource_dir() -> Path:
    """The assets/ folder. Inside a built .exe, PyInstaller unpacks it into a temporary folder."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def asset(name: str) -> str:
    return str(resource_dir() / name)


def config_root() -> Path:
    """The system folder for per-user app settings (it contains our folder)."""
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def legacy_config_dir() -> Path:
    """The settings folder of old versions (%APPDATA%\\Kotoklik). Only read or copied, never deleted."""
    return config_root() / LEGACY_APP_NAME


def _migrate_legacy(new: Path) -> Path:
    """First run after the rename: copy the old folder to the new name. Returns the folder to use."""
    old = legacy_config_dir()
    if new.exists() or not old.is_dir():
        return new
    try:
        shutil.copytree(old, new)
        return new
    except OSError:
        # could not copy (no space, no rights...): remove a half-made copy and keep using the old folder
        shutil.rmtree(new, ignore_errors=True)
        return old


def config_dir() -> Path:
    override = env("CONFIG_DIR")  # handy for tests
    if override:
        path = Path(override)
    else:
        path = _migrate_legacy(config_root() / APP_NAME)
    path.mkdir(parents=True, exist_ok=True)
    return path


def macros_dir() -> Path:
    path = config_dir() / "macros"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_dir() -> Path:
    """The app folder: next to KotoClick.exe or next to main.py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def library_dir() -> Path:
    """Macro library: the macros/ folder next to the app.
    If it is not writable (e.g. the app lives in Program Files), use
    %APPDATA%\\KotoClick\\macros. KOTOCLICK_MACROS_DIR lets you point to your own folder,
    and with KOTOCLICK_CONFIG_DIR (tests) the library lives inside that folder."""
    override = env("MACROS_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if not env("CONFIG_DIR"):
        path = app_dir() / "macros"
        if _writable(path):
            return path
    return macros_dir()


def sounds_custom_dir() -> Path:
    """Folder for trimmed custom sounds (sounds_custom/). Same rule as macros/:
    next to the app, or in the user's settings folder if that is not writable."""
    override = env("SOUNDS_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if not env("CONFIG_DIR"):
        path = app_dir() / "sounds_custom"
        if _writable(path):
            return path
    path = config_dir() / "sounds_custom"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return config_dir() / "settings.json"


def legacy_settings_file() -> Path:
    """settings.json of old versions (used for reading only if the new one does not exist yet)."""
    return legacy_config_dir() / "settings.json"
