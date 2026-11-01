"""Tests for key recording/replay and translations (no display)."""
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KOTOCLICK_CONFIG_DIR", tempfile.mkdtemp())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from kotoclick import i18n  # noqa: E402
from kotoclick.engine import Engine  # noqa: E402
from kotoclick.hotkeys import pretty_key  # noqa: E402
from kotoclick.macro import Macro, Step, release_dangling_keys  # noqa: E402
from test_core import FakeMouse, K, wait_until  # noqa: E402


class FakeKeyboard:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def press(self, step):
        with self.lock:
            self.events.append(("press", step.key_id()))

    def release(self, step):
        with self.lock:
            self.events.append(("release", step.key_id()))


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("ru")

    def test_same_keys(self):
        self.assertEqual(set(i18n.STRINGS["ru"]), set(i18n.STRINGS["en"]))

    def test_placeholders_match(self):
        import string
        f = string.Formatter()
        for k, ru in i18n.STRINGS["ru"].items():
            names = lambda s: {n for _, n, _, _ in f.parse(s) if n}  # noqa: E731
            self.assertEqual(names(ru), names(i18n.STRINGS["en"][k]), k)

    def test_switch(self):
        i18n.set_language("ru")
        self.assertEqual(Step("click", button="right", double=True).describe(), "Двойной клик правой")
        self.assertEqual(pretty_key("space"), "Пробел")
        i18n.set_language("en")
        self.assertEqual(Step("click", button="right", double=True).describe(), "Right double click")
        self.assertEqual(pretty_key("space"), "Space")
        self.assertEqual(i18n.set_language("de"), "ru")   # unknown language -> Russian

    def test_plural(self):
        i18n.set_language("ru")
        self.assertEqual([i18n.plural(n, "click") for n in (1, 2, 5, 11, 21)],
                         ["клик", "клика", "кликов", "кликов", "клик"])
        i18n.set_language("en")
        self.assertEqual([i18n.plural(n, "key") for n in (1, 2)], ["key", "keys"])


class KeyStepTests(unittest.TestCase):
    def test_roundtrip_and_describe(self):
        i18n.set_language("ru")
        m = Macro(name="k", steps=[Step("key", action="press", key="ctrl_l", delay_ms=10),
                                   Step("key", action="press", char="c", vk=67),
                                   Step("key", action="release", char="c", vk=67),
                                   Step("key", action="release", key="ctrl_l")])
        p = os.path.join(tempfile.mkdtemp(), "m.json")
        m.save(p)
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertNotIn("x", data["steps"][0])
        back = Macro.load(p)
        self.assertEqual([vars(s) for s in back.steps], [vars(s) for s in m.steps])
        self.assertEqual(back.key_count, 2)
        self.assertEqual(back.steps[0].describe(), "Нажать Ctrl")
        self.assertEqual(back.steps[2].describe(), "Отпустить C")

    def test_old_v1_file_loads(self):
        p = os.path.join(tempfile.mkdtemp(), "old.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"format": "kotoklik-macro", "version": 1, "name": "old", "steps": [
                {"kind": "click", "x": 1, "y": 2, "button": "left", "delay_ms": 5, "double": False},
                {"kind": "wait", "x": 0, "y": 0, "button": "left", "delay_ms": 50, "double": False}]}, fh)
        m = Macro.load(p)
        self.assertEqual([s.kind for s in m.steps], ["click", "wait"])
        self.assertEqual(m.key_count, 0)

    def test_bad_key_step_rejected(self):
        p = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"format": "kotoklik-macro", "version": 2, "name": "b",
                       "steps": [{"kind": "key", "action": "press"}]}, fh)
        with self.assertRaises(ValueError):
            Macro.load(p)

    def test_release_dangling(self):
        steps = release_dangling_keys([Step("key", action="press", key="shift"),
                                       Step("key", action="press", char="a", vk=65),
                                       Step("key", action="release", char="a", vk=65)])
        self.assertEqual((steps[-1].action, steps[-1].key), ("release", "shift"))
        self.assertEqual(len(steps), 4)


class KeyEngineTests(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.kb = FakeKeyboard()
        self.engine = Engine(mouse_factory=lambda: self.mouse, keyboard_factory=lambda: self.kb)

    def tearDown(self):
        self.engine.stop_all()

    def test_record_handlers_dedupe_and_exclude(self):
        e = self.engine
        e._rec_excluded = {"f6", "f7", "f8", "f9", "esc"}
        e._rec_keys_held = set()
        e._rec_steps = []
        a = K(char="a", vk=65)
        e._on_key_release(K(name="shift"))      # released a key pressed before recording: skipped
        e._on_key_press(K(name="ctrl_l"))
        e._on_key_press(a)
        e._on_key_press(a)                      # auto-repeat: skipped
        e._on_key_press(K(name="f7"))           # our own hotkey: skipped
        e._on_key_press(K(name="esc"))
        e._on_key_release(K(char="\x01", vk=65))  # Ctrl+A on Windows: a control character
        e._on_key_release(K(name="ctrl_l"))
        got = [(s.action, s.key or s.char, s.vk) for s in e._rec_steps]
        self.assertEqual(got, [("press", "ctrl_l", None), ("press", "a", 65),
                               ("release", "a", 65), ("release", "ctrl_l", None)])

    def test_playback_presses_and_releases_on_stop(self):
        m = Macro(steps=[Step("key", action="press", key="shift"),
                         Step("key", action="press", char="a", vk=65, delay_ms=5),
                         Step("wait", delay_ms=3000)])
        self.assertTrue(self.engine.start_playback(m, loops=1))
        self.assertTrue(wait_until(lambda: len(self.kb.events) >= 2))
        self.engine.stop_all()
        self.assertTrue(wait_until(lambda: not self.engine.busy))
        ev = self.kb.events
        self.assertEqual(ev[:2], [("press", ("k", "shift")), ("press", ("v", 65))])
        self.assertEqual(sorted(ev[2:]), sorted([("release", ("k", "shift")), ("release", ("v", 65))]))

    def test_playback_skips_app_hotkeys(self):
        m = Macro(steps=[Step("key", action="press", key="f8"), Step("key", action="release", key="f8"),
                         Step("key", action="press", char="b", vk=66),
                         Step("key", action="release", char="b", vk=66)])
        self.assertTrue(self.engine.start_playback(m, loops=1, skip_keys={"f6", "f7", "f8", "f9", "esc"}))
        self.assertTrue(wait_until(lambda: not self.engine.busy))
        self.assertEqual(self.kb.events, [("press", ("v", 66)), ("release", ("v", 66))])

    def test_no_keyboard_for_mouse_only_macro(self):
        def boom():
            raise AssertionError("keyboard should not be created")
        e = Engine(mouse_factory=lambda: self.mouse, keyboard_factory=boom)
        self.assertTrue(e.start_playback(Macro(steps=[Step("click", 1, 1)]), loops=1))
        self.assertTrue(wait_until(lambda: not e.busy))


if __name__ == "__main__":
    unittest.main()
