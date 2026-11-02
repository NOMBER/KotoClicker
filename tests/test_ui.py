"""UI smoke test in offscreen mode (the window is not shown)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["KOTOCLICK_SOUND"] = "off"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as app_main  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.hotkeys import HotkeyListener  # noqa: E402
from app.macro import Macro, Step  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from test_core import FakeMouse, wait_until  # noqa: E402

APP = app_main.create_app([])


class UiTests(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.engine = Engine(mouse_factory=lambda: self.mouse)
        self.win = MainWindow(Settings(language="ru"), self.engine, HotkeyListener())
        self.win.show()

    def tearDown(self):
        self.win.close()

    def test_hotkey_toggles_clicking(self):
        w = self.win
        self.assertEqual(w.status_title.text().replace("\xa0", " "), "Котик дремлет…")
        w.on_hotkey("f6")
        self.assertEqual(w.state, "clicking")
        self.assertEqual(w.status_title.text().replace("\xa0", " "), "Котик кликает за тебя!")
        self.assertTrue(wait_until(lambda: self.engine.clicks > 2))
        w.on_hotkey("esc")
        self.assertEqual(w.state, "idle")
        self.assertTrue(wait_until(lambda: not self.engine.busy))

    def test_paw_button_countdown(self):
        w = self.win
        w.paw.click()
        self.assertEqual(w.state, "countdown")
        self.assertTrue(wait_until(lambda: w.state == "clicking", timeout=5))
        w.paw.click()
        self.assertEqual(w.state, "idle")

    def test_finite_clicks_return_to_idle(self):
        w = self.win
        w.settings.repeat_forever = False
        w.settings.repeat_count = 3
        w.on_hotkey("f6")
        self.assertTrue(wait_until(lambda: w.state == "idle"))
        self.assertEqual(self.engine.clicks, 3)

    def test_playback_hotkey(self):
        w = self.win
        w.on_hotkey("f8")
        self.assertEqual(w.state, "idle", "пустой макрос не запускается")
        w._set_macro(Macro("m", [Step("click", 3, 4, delay_ms=5)]))
        w.settings.macro_loop = False
        w.settings.macro_repeat_count = 2
        w.on_hotkey("f8")
        self.assertEqual(w.state, "playing")
        self.assertEqual(w.status_title.text().replace("\xa0", " "), "Котик повторяет за мышкой")
        self.assertTrue(wait_until(lambda: w.state == "idle"))
        self.assertEqual(self.engine.clicks, 2)

    def test_key_capture_and_conflict(self):
        w = self.win
        w._begin_capture(w.key_click)
        self.assertEqual(w.key_click.text(), "Нажми клавишу…")
        w.on_key_captured("f8")             # taken by "repeat"
        self.assertEqual(w.settings.hotkey_click, "f6")
        w._begin_capture(w.key_click)
        w.on_key_captured("g")
        self.assertEqual(w.settings.hotkey_click, "g")
        self.assertEqual(w.key_click.text(), "G")
        w.on_hotkey("g")
        self.assertEqual(w.state, "clicking")
        w.panic()

    def test_table_editing(self):
        w = self.win
        w._set_macro(Macro("m", [Step("click", 1, 2, delay_ms=10), Step("wait", delay_ms=20)]))
        self.assertEqual(w.table.rowCount(), 2)
        w.table.item(0, 4).setText("777")
        self.assertEqual(w.macro.steps[0].delay_ms, 777)
        w.table.item(0, 2).setText("55")
        self.assertEqual(w.macro.steps[0].x, 55)
        w.table.selectRow(1)
        w._delete_steps()
        self.assertEqual(len(w.macro.steps), 1)
        w._add_wait_step()
        self.assertEqual(w.macro.steps[-1].kind, "wait")

    def test_settings_persist_on_close(self):
        w = self.win
        w.click_type.set_value("double")
        w._set("double_click", True)
        w.close()
        self.assertTrue(Settings.load().double_click)


if __name__ == "__main__":
    unittest.main()
