"""Task 7 tests: holding mouse buttons, drag & drop and the mouse wheel.

Everything runs with fake pynput objects and a fake clock, so no real input is sent."""
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KOTOCLICK_CONFIG_DIR", tempfile.mkdtemp())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import engine as engine_mod, i18n  # noqa: E402
from app.engine import Engine, PynputMouse  # noqa: E402
from app.macro import FORMAT_VERSION, Macro, Step, release_dangling_buttons  # noqa: E402
from test_core import K, wait_until  # noqa: E402
from test_keys import FakeKeyboard  # noqa: E402

APP = QApplication.instance() or QApplication([])


class B:
    """A pynput-like mouse button."""

    def __init__(self, name):
        self.name = name


class FakeMouse:
    """Fake mouse with press / release / scroll; records every call in order."""

    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
        self.position = (0, 0)
        self.pressed = threading.Event()

    def move_to(self, x, y):
        with self.lock:
            self.position = (x, y)
            self.events.append(("move", x, y))

    def click(self, button="left", count=1):
        with self.lock:
            self.events.append(("click", button, count))

    def press(self, button="left"):
        with self.lock:
            self.events.append(("press", button))
        self.pressed.set()

    def release(self, button="left"):
        with self.lock:
            self.events.append(("release", button))

    def scroll(self, dx=0, dy=0):
        with self.lock:
            self.events.append(("scroll", dx, dy))


class FakeListener:
    """Stands in for pynput.mouse.Listener / keyboard.Listener: only keeps the callbacks."""
    instances = []

    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.daemon = False
        FakeListener.instances.append(self)

    def start(self):
        pass

    def stop(self):
        pass


class Clock:
    """A fake time.perf_counter driven by the test."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def tick(self, seconds):
        self.t += seconds


class RecordingTests(unittest.TestCase):
    def setUp(self):
        FakeListener.instances = []
        self.clock = Clock()
        fake_mouse_mod = types.SimpleNamespace(Listener=FakeListener)
        fake_kb_mod = types.SimpleNamespace(Listener=FakeListener)
        self.patches = [
            mock.patch.object(engine_mod.time, "perf_counter", self.clock),
            mock.patch.object(engine_mod, "_pynput_mouse", lambda: fake_mouse_mod),
            mock.patch.object(engine_mod, "_pynput_keyboard", lambda: fake_kb_mod),
        ]
        for p in self.patches:
            p.start()
        self.engine = Engine(mouse_factory=FakeMouse)
        self.recorded = []
        self.engine.stepRecorded.connect(self.recorded.append)

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def start(self, moves=False, keys=False):
        self.assertTrue(self.engine.start_recording(record_moves=moves, record_keys=keys))
        cb = FakeListener.instances[0].callbacks
        self.assertIn("on_scroll", cb)          # the wheel is subscribed
        return cb

    def test_quick_click_is_one_click_step(self):
        cb = self.start()
        self.clock.tick(0.5)
        cb["on_click"](100, 100, B("left"), True)
        self.clock.tick(0.08)
        cb["on_move"](102, 101)                 # jitter below 5 px is ignored
        cb["on_click"](102, 101, B("left"), False)
        steps = self.engine.stop_recording()
        self.assertEqual([(s.kind, s.x, s.y, s.button, s.delay_ms) for s in steps],
                         [("click", 100, 100, "left", 500)])

    def test_long_hold_without_moving(self):
        cb = self.start()
        self.clock.tick(0.2)
        cb["on_click"](50, 60, B("right"), True)
        self.clock.tick(0.8)
        cb["on_click"](50, 60, B("right"), False)
        self.clock.tick(0.1)
        cb["on_click"](70, 80, B("left"), True)
        self.clock.tick(0.05)
        cb["on_click"](70, 80, B("left"), False)
        steps = self.engine.stop_recording()
        self.assertEqual([(s.kind, s.button, s.delay_ms) for s in steps],
                         [("mouse_down", "right", 200), ("mouse_up", "right", 800), ("click", "left", 100)])

    def test_drag_with_moves_on(self):
        cb = self.start(moves=True)
        self.clock.tick(0.3)
        cb["on_click"](10, 10, B("left"), True)
        for i in range(1, 6):
            self.clock.tick(0.03)
            cb["on_move"](10 + 20 * i, 10)
        self.clock.tick(0.03)
        cb["on_click"](110, 10, B("left"), False)
        steps = self.engine.stop_recording()
        kinds = [s.kind for s in steps]
        self.assertEqual(kinds[0], "mouse_down")
        self.assertEqual(kinds[-1], "mouse_up")
        self.assertEqual(set(kinds[1:-1]), {"move"})
        self.assertEqual(len(kinds), 7)
        self.assertEqual((steps[0].x, steps[0].y, steps[0].delay_ms), (10, 10, 300))
        self.assertEqual((steps[-1].x, steps[-1].y), (110, 10))
        self.assertEqual(sum(s.delay_ms for s in steps), 300 + 6 * 30)   # no time lost
        self.assertEqual(self.recorded, steps)                            # UI got them in order

    def test_drag_with_moves_off_is_sampled(self):
        cb = self.start(moves=False)
        cb["on_move"](0, 0)                      # moves without a button: not recorded
        self.clock.tick(0.1)
        cb["on_click"](0, 0, B("left"), True)
        for i in range(1, 21):                   # 20 events, 10 ms apart = 200 ms of dragging
            self.clock.tick(0.01)
            cb["on_move"](10 * i, 0)
        self.clock.tick(0.01)
        cb["on_click"](200, 0, B("left"), False)
        self.clock.tick(0.1)
        cb["on_move"](300, 300)                  # released again: not recorded
        steps = self.engine.stop_recording()
        kinds = [s.kind for s in steps]
        self.assertEqual(kinds[0], "mouse_down")
        self.assertEqual(kinds[-1], "mouse_up")
        moves = kinds.count("move")
        self.assertTrue(2 <= moves <= 5, moves)  # sampled every DRAG_SAMPLE_S, not every event

    def test_scroll_coalescing(self):
        cb = self.start()
        self.clock.tick(0.4)
        for _ in range(3):
            cb["on_scroll"](300, 200, 0, -1)
            self.clock.tick(0.03)
        self.clock.tick(0.3)                     # a pause: new step
        cb["on_scroll"](300, 200, 0, -1)
        self.clock.tick(0.02)
        cb["on_scroll"](300, 200, 0, 1)          # opposite direction: not merged
        self.clock.tick(0.02)
        cb["on_scroll"](400, 200, 0, 1)          # another spot: not merged
        steps = self.engine.stop_recording()
        self.assertEqual([(s.kind, s.dy, s.delay_ms) for s in steps],
                         [("scroll", -3, 400), ("scroll", -1, 390), ("scroll", 1, 20), ("scroll", 1, 20)])
        # the merged step was re-sent to the UI as the same object
        self.assertIs(self.recorded[0], self.recorded[2])
        self.assertEqual(len({id(s) for s in self.recorded}), 4)

    def test_scroll_while_holding_promotes_press(self):
        cb = self.start()
        cb["on_click"](5, 5, B("left"), True)
        self.clock.tick(0.05)
        cb["on_scroll"](5, 5, 0, 2)
        self.clock.tick(0.05)
        cb["on_click"](5, 5, B("left"), False)
        steps = self.engine.stop_recording()
        self.assertEqual([s.kind for s in steps], ["mouse_down", "scroll", "mouse_up"])

    def test_key_during_press_keeps_order(self):
        cb = self.start(keys=True)
        kcb = FakeListener.instances[1].callbacks
        cb["on_click"](5, 5, B("left"), True)
        self.clock.tick(0.05)
        kcb["on_press"](K(name="shift"))
        self.clock.tick(0.05)
        kcb["on_release"](K(name="shift"))
        cb["on_click"](5, 5, B("left"), False)
        steps = self.engine.stop_recording()
        self.assertEqual([s.kind for s in steps], ["mouse_down", "key", "key", "mouse_up"])

    def test_stuck_button_gets_mouse_up_at_stop(self):
        cb = self.start(moves=True)
        cb["on_click"](10, 10, B("left"), True)
        self.clock.tick(0.1)
        cb["on_move"](60, 60)
        self.clock.tick(2.0)
        steps = self.engine.stop_recording()     # stopped by the hotkey while still held
        self.assertEqual([s.kind for s in steps], ["mouse_down", "move", "mouse_up"])
        self.assertEqual((steps[-1].x, steps[-1].y, steps[-1].button), (60, 60, "left"))

    def test_stuck_pending_press_gets_mouse_up_at_stop(self):
        cb = self.start()
        cb["on_click"](10, 10, B("middle"), True)
        self.clock.tick(0.1)
        steps = self.engine.stop_recording()
        self.assertEqual([(s.kind, s.button) for s in steps], [("mouse_down", "middle"), ("mouse_up", "middle")])

    def test_stop_button_press_dropped(self):
        cb = self.start()
        cb["on_click"](10, 10, B("left"), True)
        self.clock.tick(0.05)
        cb["on_click"](10, 10, B("left"), False)
        self.clock.tick(1.5)
        cb["on_click"](900, 700, B("left"), True)    # pressing "Stop" in KotoClick's window
        self.clock.tick(0.05)
        steps = self.engine.stop_recording(drop_last_click_within=1.0)
        self.assertEqual([s.kind for s in steps], ["click"])

    def test_stop_button_long_press_dropped(self):
        cb = self.start()
        cb["on_click"](10, 10, B("left"), True)
        self.clock.tick(0.05)
        cb["on_click"](10, 10, B("left"), False)
        self.clock.tick(1.5)
        cb["on_click"](900, 700, B("left"), True)
        self.clock.tick(0.4)                         # held a bit longer than a click
        cb["on_click"](900, 700, B("left"), False)
        steps = self.engine.stop_recording(drop_last_click_within=1.0)
        self.assertEqual([s.kind for s in steps], ["click"])

    def test_release_of_button_pressed_before_recording_is_ignored(self):
        cb = self.start()
        cb["on_click"](10, 10, B("left"), False)
        self.assertEqual(self.engine.stop_recording(), [])


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.kb = FakeKeyboard()
        self.engine = Engine(mouse_factory=lambda: self.mouse, keyboard_factory=lambda: self.kb)
        self.stopped = []
        self.engine.playerStopped.connect(lambda: self.stopped.append("player"))

    def tearDown(self):
        self.engine.stop_all()

    def test_replay_order(self):
        m = Macro(steps=[Step("mouse_down", 10, 20, "left"), Step("move", 30, 40),
                         Step("mouse_up", 50, 60, "left"), Step("scroll", 70, 80, dx=1, dy=-3),
                         Step("click", 1, 2, "right")])
        self.assertTrue(self.engine.start_playback(m, loops=1))
        self.assertTrue(wait_until(lambda: self.stopped == ["player"]))
        self.assertEqual(self.mouse.events, [
            ("move", 10, 20), ("press", "left"), ("move", 30, 40), ("move", 50, 60), ("release", "left"),
            ("move", 70, 80), ("scroll", 1, -3), ("move", 1, 2), ("click", "right", 1)])
        self.assertEqual(self.engine.clicks, 2)      # a hold counts once, scroll does not count

    def test_held_button_released_on_stop(self):
        m = Macro(steps=[Step("mouse_down", 10, 20, "right"), Step("wait", delay_ms=10_000),
                         Step("mouse_up", 10, 20, "right")])
        self.assertTrue(self.engine.start_playback(m, loops=1))
        self.assertTrue(self.mouse.pressed.wait(2))
        self.engine.stop_all()                       # what Stop / panic do
        self.assertTrue(wait_until(lambda: self.stopped == ["player"]))
        self.assertEqual(self.mouse.events[-1], ("release", "right"))
        self.assertEqual([e for e in self.mouse.events if e[0] == "release"], [("release", "right")])

    def test_mouse_only_macro_needs_no_keyboard(self):
        def boom():
            raise RuntimeError("no keyboard")
        e = Engine(mouse_factory=lambda: self.mouse, keyboard_factory=boom)
        done = []
        e.playerStopped.connect(lambda: done.append(1))
        self.assertTrue(e.start_playback(Macro(steps=[Step("scroll", 1, 1, dy=1)]), loops=1))
        self.assertTrue(wait_until(lambda: done == [1]))


class PynputWrapperTests(unittest.TestCase):
    def test_press_release_scroll(self):
        calls = []

        class Ctl:
            position = (0, 0)

            def press(self, b):
                calls.append(("press", b))

            def release(self, b):
                calls.append(("release", b))

            def scroll(self, dx, dy):
                calls.append(("scroll", dx, dy))

        fake = types.SimpleNamespace(Controller=Ctl,
                                     Button=types.SimpleNamespace(left="L", right="R", middle="M"))
        with mock.patch.object(engine_mod, "_pynput_mouse", lambda: fake):
            m = PynputMouse()
        m.press("middle")
        m.release("middle")
        m.scroll(0, -2)
        self.assertEqual(calls, [("press", "M"), ("release", "M"), ("scroll", 0, -2)])


class MacroFormatTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("ru")

    def test_old_files_load(self):
        v1 = {"app": "Kotoklik", "version": 1, "name": "old",
              "steps": [{"kind": "click", "x": 1, "y": 2, "button": "left", "delay_ms": 10}]}
        v2 = {"app": "KotoClick", "version": 2, "name": "old2",
              "steps": [{"kind": "move", "x": 3, "y": 4, "delay_ms": 5},
                        {"kind": "key", "action": "press", "key": "shift", "delay_ms": 0},
                        {"kind": "key", "action": "release", "key": "shift", "delay_ms": 0}]}
        for d in (v1, v2):
            path = os.path.join(tempfile.mkdtemp(), "m.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(d, fh)
            m = Macro.load(path)
            self.assertEqual(len(m.steps), len(d["steps"]))
        with self.assertRaises(ValueError):
            Macro.from_dict({"steps": [{"kind": "teleport"}]})

    def test_v3_roundtrip(self):
        m = Macro("drag", [Step("mouse_down", 1, 2, "middle", 100), Step("move", 5, 6, delay_ms=50),
                           Step("mouse_up", 7, 8, "middle", 50), Step("scroll", 9, 10, delay_ms=20, dx=-1, dy=4)])
        path = os.path.join(tempfile.mkdtemp(), "m.json")
        m.save(path)
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw["version"], FORMAT_VERSION)
        self.assertEqual(FORMAT_VERSION, 3)
        self.assertNotIn("dx", raw["steps"][0])
        self.assertEqual((raw["steps"][3]["dx"], raw["steps"][3]["dy"]), (-1, 4))
        back = Macro.load(path)
        self.assertEqual(back.steps, m.steps)
        self.assertEqual(back.click_count, 1)

    def test_describe(self):
        i18n.set_language("ru")
        self.assertEqual(Step("mouse_down", button="left").describe(), "Зажать левую кнопку")
        self.assertEqual(Step("mouse_up", button="right").describe(), "Отпустить правую кнопку")
        self.assertEqual(Step("scroll", dy=3).describe(), "Прокрутка вверх ×3")
        self.assertEqual(Step("scroll", dy=-2, dx=1).describe(), "Прокрутка вниз ×2, вправо ×1")
        i18n.set_language("en")
        self.assertEqual(Step("mouse_down", button="middle").describe(), "Hold middle button")
        self.assertEqual(Step("mouse_up", button="left").describe(), "Release left button")
        self.assertEqual(Step("scroll", dy=-4).describe(), "Scroll down ×4")
        self.assertEqual(Step("scroll", dx=-1).describe(), "Scroll left ×1")

    def test_release_dangling_buttons(self):
        out = release_dangling_buttons([Step("mouse_down", 1, 1, "left"), Step("move", 9, 9),
                                        Step("mouse_down", 2, 2, "right"), Step("mouse_up", 3, 3, "right")])
        self.assertEqual([(s.kind, s.button, s.x, s.y) for s in out[-1:]], [("mouse_up", "left", 3, 3)])


class StepDialogTests(unittest.TestCase):
    def test_edit_scroll_and_hold(self):
        from app.ui.step_dialog import StepDialog
        d = StepDialog(Step("scroll", 10, 20, delay_ms=30, dx=0, dy=-2), cursor_fn=lambda: (0, 0))
        self.assertTrue(d.dy.isEnabled())
        self.assertFalse(d.button.isEnabled())
        d.dy.setValue(5)
        s = d.result_step()
        self.assertEqual((s.kind, s.x, s.y, s.dy, s.delay_ms), ("scroll", 10, 20, 5, 30))
        d.kind.set_value("mouse_down")
        d._sync()
        self.assertTrue(d.button.isEnabled())
        self.assertFalse(d.dy.isEnabled())
        self.assertFalse(d.double.isEnabled())
        s = d.result_step()
        self.assertEqual((s.kind, s.dx, s.dy, s.double), ("mouse_down", 0, 0, False))


if __name__ == "__main__":
    unittest.main()
