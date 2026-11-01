"""KotoClick (Russian name: Kotoklik) entry point. Run: python main.py"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from kotoclick import paths
from kotoclick.engine import Engine
from kotoclick.hotkeys import HotkeyListener
from kotoclick.settings import Settings
from kotoclick.ui import theme
from kotoclick.ui.main_window import MainWindow


def dark_title_bar(window):
    """Dark window frame on Windows 10/11 (a normal window-styling call, no registry)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new and old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:  # noqa: BLE001 - did not work, never mind: just a light frame
        pass


def create_app(argv=None):
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("KotoClick")
    app.setApplicationDisplayName("Котоклик")
    app.setWindowIcon(QIcon(paths.asset("kotoclick.ico")))
    # Our friendly Nunito font (in assets/fonts, OFL licence)
    fid = QFontDatabase.addApplicationFont(paths.asset("fonts/Nunito-VariableFont_wght.ttf"))
    families = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    if families:
        theme.FONT_FAMILY = families[0]
        theme.STYLESHEET = theme.STYLESHEET.replace('"Nunito"', f'"{families[0]}"')
    f = QFont(theme.FONT_FAMILY)
    f.setPixelSize(14)
    f.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(f)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    return app


def build_window(app):
    settings = Settings.load()
    engine = Engine()
    hotkeys = HotkeyListener()
    win = MainWindow(settings, engine, hotkeys)
    # Signals from the pynput thread -> Qt main thread (QueuedConnection = thread-safe)
    hotkeys.hotkeyPressed.connect(win.on_hotkey, Qt.QueuedConnection)
    hotkeys.keyCaptured.connect(win.on_key_captured, Qt.QueuedConnection)
    hotkeys.failed.connect(win.on_hotkeys_failed, Qt.QueuedConnection)
    return win, hotkeys


def main():
    app = create_app()
    win, hotkeys = build_window(app)
    win.show()
    dark_title_bar(win)
    hotkeys.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
