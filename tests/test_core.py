"""KotoClick logic tests (no display). Run: python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KOTOCLICK_CONFIG_DIR", tempfile.mkdtemp())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from kotoclick.engine import Engine  # noqa: E402
from kotoclick.hotkeys import HotkeyListener, key_to_name, pretty_key  # noqa: E402
from kotoclick.macro import Macro, Step, compress_moves  # noqa: E402
from kotoclick.settings import Settings  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakeMouse:
    """Fake mouse: remembers what it was asked to do."""

    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
        self.position = (5, 5)

    def move_to(self, x, y):
        with self.lock:
            self.position = (x, y)
            self.events.append(("move", x, y))

    def click(self, button="left", count=1):
        with self.lock:
            self.events.append(("click", button, count, self.position))


def wait_until(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        APP.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return False


class MacroTests(unittest.TestCase):
    def test_roundtrip(self):
        m = Macro("Тест", [Step("click", 10, 20, "right", 150, double=True), Step("wait", delay_ms=500),
                           Step("move", 1, 2, delay_ms=16)])
        path = os.path.join(tempfile.mkdtemp(), "m.json")
        m.save(path)
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw["app"], "KotoClick")
        self.assertEqual(raw["steps"][1], {"kind": "wait", "delay_ms": 500})
        m2 = Macro.load(path)
        self.assertEqual(m2, m)
        self.assertEqual(m2.click_count, 1)
        self.assertEqual(m2.duration_ms, 666)

    def test_rejects_garbage(self):
        for bad in ({}, {"steps": "x"}, {"steps": [{"kind": "explode"}]}, {"steps": [{"kind": "click", "button": "x"}]}, []):
            with self.assertRaises((ValueError, TypeError)):
                Macro.from_dict(bad)

    def test_negative_delay_clamped(self):
        self.assertEqual(Step.from_dict({"kind": "wait", "delay_ms": -5}).delay_ms, 0)

    def test_compress_moves(self):
        steps = [Step("move", 0, 0, delay_ms=10), Step("move", 1, 1, delay_ms=10), Step("move", 2, 2, delay_ms=10),
                 Step("move", 50, 50, delay_ms=10), Step("click", 50, 50, delay_ms=5)]
        out = compress_moves(steps)
        self.assertEqual([s.kind for s in out], ["move", "move", "click"])
        self.assertEqual((out[0].x, out[0].y, out[0].delay_ms), (2, 2, 30))
        self.assertEqual(sum(s.delay_ms for s in out), sum(s.delay_ms for s in steps))
        self.assertEqual(steps[0].x, 0, "исходный список не должен меняться")

    def test_describe(self):
        self.assertEqual(Step("click", button="right", double=True).describe(), "Двойной клик правой")
        self.assertEqual(Step("wait").describe(), "Пауза")


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_defaults(self):
        path = os.path.join(tempfile.mkdtemp(), "s.json")
        s = Settings(hotkey_click="f2", interval_value=2, interval_unit="s", button="middle")
        s.save(path)
        s2 = Settings.load(path)
        self.assertEqual(s2, s)
        self.assertAlmostEqual(s2.interval_seconds, 2.0)
        self.assertEqual(Settings.load(path + ".missing"), Settings())

    def test_validation(self):
        s = Settings.from_dict({"interval_unit": "years", "button": "nose", "interval_value": -3,
                                "repeat_count": 0, "unknown": 1, "hotkey_play": ""})
        self.assertEqual(s.interval_unit, "ms")
        self.assertEqual(s.button, "left")
        self.assertEqual(s.interval_value, 1.0)
        self.assertEqual(s.repeat_count, 1)
        self.assertEqual(s.hotkey_play, "f8")

    def test_broken_file(self):
        path = os.path.join(tempfile.mkdtemp(), "s.json")
        with open(path, "w") as fh:
            fh.write("{ broken")
        self.assertEqual(Settings.load(path), Settings())


class K:
    def __init__(self, name=None, char=None, vk=None):
        self.name, self.char, self.vk = name, char, vk


class HotkeyTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(key_to_name(K(name="f6")), "f6")
        self.assertEqual(key_to_name(K(char="Q")), "q")
        self.assertEqual(pretty_key("f6"), "F6")
        self.assertEqual(pretty_key("esc"), "Esc")
        self.assertEqual(pretty_key("q"), "Q")
        self.assertEqual(pretty_key("space"), "Пробел")

    def test_listener_filters_and_dedups(self):
        hk = HotkeyListener()
        got, captured = [], []
        hk.hotkeyPressed.connect(got.append)
        hk.keyCaptured.connect(captured.append)
        hk.set_watched({"f6"})
        hk._on_press(K(name="f5"))            # not assigned: ignored
        hk._on_press(K(name="f6"))
        hk._on_press(K(name="f6"))            # auto-repeat of a held key: ignored
        hk._on_release(K(name="f6"))
        hk._on_press(K(name="f6"))            # "bounce" (<150 ms): ignored
        hk._on_release(K(name="f6"))
        time.sleep(0.2)
        hk._on_press(K(name="f6"))
        hk.begin_capture()
        hk._on_press(K(char="x"))
        APP.processEvents()
        self.assertEqual(got, ["f6", "f6"])
        self.assertEqual(captured, ["x"])

    def test_signal_from_other_thread(self):
        hk = HotkeyListener()
        got = []
        hk.hotkeyPressed.connect(got.append)
        hk.set_watched({"f9"})
        t = threading.Thread(target=hk._on_press, args=(K(name="f9"),))
        t.start()
        t.join()
        self.assertTrue(wait_until(lambda: got == ["f9"]))


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.engine = Engine(mouse_factory=lambda: self.mouse)
        self.stopped = []
        self.engine.clickerStopped.connect(lambda: self.stopped.append("clicker"))
        self.engine.playerStopped.connect(lambda: self.stopped.append("player"))

    def tearDown(self):
        self.engine.stop_all()

    def test_click_n_times(self):
        t0 = time.perf_counter()
        self.assertTrue(self.engine.start_clicking(0.02, "right", True, repeat=10))
        self.assertTrue(wait_until(lambda: self.stopped == ["clicker"]))
        elapsed = time.perf_counter() - t0
        self.assertEqual(self.engine.clicks, 10)
        self.assertEqual(len(self.mouse.events), 10)
        self.assertEqual(self.mouse.events[0], ("click", "right", 2, (5, 5)))
        self.assertGreater(elapsed, 0.17)    # 9 intervals of 20 ms
        self.assertLess(elapsed, 1.0)

    def test_click_until_stopped(self):
        self.engine.start_clicking(0.005)
        self.assertFalse(self.engine.start_clicking(0.005), "второй запуск поверх первого запрещён")
        time.sleep(0.1)
        t0 = time.perf_counter()
        self.engine.stop_all()
        self.assertLess(time.perf_counter() - t0, 0.5)
        self.assertTrue(wait_until(lambda: self.stopped == ["clicker"]))
        n = self.engine.clicks
        self.assertGreater(n, 5)
        time.sleep(0.05)
        self.assertEqual(self.engine.clicks, n, "после стопа кликов больше нет")

    def test_playback_loops(self):
        m = Macro(steps=[Step("click", 10, 20, delay_ms=10), Step("wait", delay_ms=10),
                         Step("move", 30, 40, delay_ms=0), Step("click", 50, 60, "middle", 5)])
        self.assertTrue(self.engine.start_playback(m, loops=3))
        self.assertTrue(wait_until(lambda: self.stopped == ["player"]))
        clicks = [e for e in self.mouse.events if e[0] == "click"]
        self.assertEqual(len(clicks), 6)
        self.assertEqual(clicks[0], ("click", "left", 1, (10, 20)))
        self.assertEqual(clicks[1], ("click", "middle", 1, (50, 60)))
        self.assertIn(("move", 30, 40), self.mouse.events)

    def test_stop_during_long_wait(self):
        m = Macro(steps=[Step("click", 1, 1, delay_ms=60_000)])
        self.engine.start_playback(m)
        time.sleep(0.05)
        t0 = time.perf_counter()
        self.engine.stop_all()
        self.assertLess(time.perf_counter() - t0, 0.5, "стоп-кран срабатывает сразу, даже в длинной паузе")
        self.assertTrue(wait_until(lambda: self.stopped == ["player"]))
        self.assertEqual(self.mouse.events, [])

    def test_empty_macro_not_started(self):
        self.assertFalse(self.engine.start_playback(Macro()))

    def test_restart_right_after_stop(self):
        self.engine.start_clicking(0.01)
        time.sleep(0.03)
        self.engine.stop_all()
        self.assertTrue(self.engine.start_clicking(0.01, repeat=2))

    def test_recorder_callbacks(self):
        # Test recording without a real mouse: call the callbacks directly
        e = self.engine
        recorded = []
        e.stepRecorded.connect(recorded.append)
        e._rec_steps, e._rec_moves, e._rec_last, e._rec_last_move = [], True, time.perf_counter(), 0.0

        class B:
            def __init__(self, n):
                self.name = n
        time.sleep(0.05)
        e._on_move(100, 100)
        e._on_click(110, 120, B("left"), True)
        e._on_click(110, 120, B("left"), False)   # quick press + release = one click step
        e._on_click(1, 1, B("x1"), True)           # side buttons are not recorded
        time.sleep(0.03)
        e._on_click(200, 220, B("right"), True)
        e._on_click(200, 220, B("right"), False)
        steps = e.stop_recording()
        self.assertEqual([s.kind for s in steps], ["move", "click", "click"])
        self.assertGreaterEqual(steps[0].delay_ms, 40)
        self.assertGreaterEqual(steps[2].delay_ms, 25)
        self.assertEqual((steps[2].x, steps[2].y, steps[2].button), (200, 220, "right"))
        APP.processEvents()
        self.assertEqual(len(recorded), 3)

    def test_recorder_drops_stop_click(self):
        e = self.engine

        class B:
            name = "left"
        e._rec_steps, e._rec_moves, e._rec_last = [], False, time.perf_counter()
        e._on_click(5, 5, B(), True)
        e._on_click(5, 5, B(), False)
        e._on_click(6, 6, B(), True)               # the click on the "Stop" button itself
        e._on_click(6, 6, B(), False)
        steps = e.stop_recording(drop_last_click_within=1.0)
        self.assertEqual(len(steps), 1)



class HotkeyLostReleaseTest(unittest.TestCase):
    def test_lost_release_recovers(self):
        import kotoclick.hotkeys as hk_mod
        hk = HotkeyListener()
        got = []
        hk.hotkeyPressed.connect(got.append)
        hk.set_watched({"f8"})
        hk._on_press(K(name="f8"))       # the release got "lost"
        hk._held["f8"] -= hk_mod.REPEAT_WINDOW + 0.1   # more than a second passed
        hk._last_fire["f8"] -= hk_mod.REPEAT_WINDOW + 0.1
        hk._on_press(K(name="f8"))
        APP.processEvents()
        self.assertEqual(got, ["f8", "f8"])


if __name__ == "__main__":
    unittest.main()
