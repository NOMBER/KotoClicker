"""UI: language switching, the "Record keystrokes" switch, fixed size."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["KOTOCLICK_SOUND"] = "off"

import main as app_main  # noqa: E402
from app import i18n  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.hotkeys import HotkeyListener  # noqa: E402
from app.macro import Step  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.ui.main_window import WIN_H, WIN_W, MainWindow, COL_ACT, COL_X  # noqa: E402
from test_core import FakeMouse  # noqa: E402

APP = app_main.create_app([])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LangUiTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(mouse_factory=FakeMouse)
        self.win = MainWindow(Settings(language="ru"), self.engine, HotkeyListener())
        self.win.show()

    def tearDown(self):
        self.win.close()
        i18n.set_language("ru")

    def test_fixed_size(self):
        self.assertEqual((self.win.width(), self.win.height()), (WIN_W, WIN_H))
        self.assertEqual(self.win.minimumSize(), self.win.maximumSize())
        self.assertFalse(self.win.windowFlags() & app_main.Qt.WindowMaximizeButtonHint)

    def test_live_language_switch_and_persist(self):
        w = self.win
        self.assertEqual(w.tab_buttons[1].text(), "Мышкины макросы")
        w.lang_seg.buttons()[1].click()          # the EN button
        self.assertEqual(i18n.language(), "en")
        self.assertEqual(w.settings.language, "en")
        self.assertEqual(w.tab_buttons[1].text(), "Mouse's macros")
        self.assertEqual(w.status_title.text().replace("\xa0", " "), "The cat is napping…")
        self.assertEqual(w.record_keys.text(), "Record keystrokes")
        self.assertIn("KotoClick", w.windowTitle())
        w._save_settings()
        self.assertEqual(Settings.load().language, "en")
        w.set_language("ru")
        self.assertEqual(w.record_keys.text(), "Записывать клавиши")

    def test_key_steps_in_table(self):
        w = self.win
        w.macro.steps = [Step("key", action="press", key="ctrl_l"), Step("key", action="release", key="ctrl_l")]
        w._fill_table()
        self.assertEqual(w.table.item(0, COL_ACT).text(), "⌨  Нажать Ctrl")
        self.assertEqual(w.table.item(1, COL_ACT).text(), "⌨  Отпустить Ctrl")
        self.assertEqual(w.table.item(0, COL_X).text(), "—")
        self.assertIn("1", w.macro_stats.text())
        w.set_language("en")
        self.assertEqual(w.table.item(0, COL_ACT).text(), "⌨  Press Ctrl")

    def test_record_keys_passed_to_engine(self):
        w = self.win
        calls = []
        w.engine.start_recording = lambda *a, **kw: calls.append((a, kw)) or True
        w.record_keys.setChecked(True)
        w.toggle_recording()
        self.assertEqual(w.state, "countdown")      # first a 3-second countdown
        self.assertEqual(calls, [])
        for _ in range(3):
            w._countdown_tick()
        a, kw = calls[0]
        self.assertEqual(a, (False, True))
        self.assertEqual(kw["excluded_keys"], {"f6", "f7", "f8", "f9", "esc"})
        w.state = "idle"


class LayoutCheck(unittest.TestCase):
    def test_no_clipped_text_at_windows_scales(self):
        for scale in ("1", "1.25", "1.5"):
            env = dict(os.environ, QT_SCALE_FACTOR=scale)
            env.pop("QT_QPA_PLATFORM", None)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_layout.py")],
                               env=env, capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
