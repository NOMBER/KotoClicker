"""Cat reactions, macro library, sounds, the Telegram bot bubble, countdown before recording."""
import json
import os
import random
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["KOTOCLICK_SOUND"] = "off"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import promo  # noqa: E402
from app.library import MacroLibrary, safe_name  # noqa: E402
from app.macro import Macro, Step  # noqa: E402
from app.reactions import ClickRate, HatWiggle, Mood  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.sounds import EVENTS, SoundBoard, check_wav, default_path, scaled_wav  # noqa: E402


def run_mood(mood, cps, start, seconds, step=0.05, allowed=True):
    t = start
    while t < start + seconds - 1e-9:
        t += step
        mood.update(cps, t, allowed)
    return t


class ReactionsTests(unittest.TestCase):
    def test_click_rate(self):
        r = ClickRate()
        total, t = 0, 0.0
        for _ in range(40):              # 20 clicks/s
            t += 0.05
            total += 1
            r.feed(total, t)
        self.assertAlmostEqual(r.cps, 20, delta=2)
        self.assertEqual(r.feed(total + 5, t + 0.05), 5)
        r.feed(0, t + 0.1)               # the counter was reset: the rate is not negative
        self.assertEqual(r.cps, 0)

    def test_disco_needs_fast_and_long(self):
        m = Mood()
        t = run_mood(m, 20, 0, 4.0)
        self.assertEqual(m.state, "hyper")          # 4 s is not enough
        self.assertFalse(m.disco)
        t = run_mood(m, 20, t, 1.2)
        self.assertTrue(m.disco)
        self.assertEqual(m.state, "disco")
        t = run_mood(m, 20, t, 1.5)
        self.assertAlmostEqual(m.intensity, 1.0)

    def test_moods_by_rate(self):
        m = Mood()
        self.assertEqual(m.update(1, 0), "calm")
        self.assertEqual(m.update(5, 0.1), "lively")
        self.assertEqual(m.update(12, 0.2), "hyper")

    def test_slowdown_interrupts_build_up(self):
        m = Mood()
        t = run_mood(m, 20, 0, 3.0)
        t = run_mood(m, 5, t, 0.2)
        t = run_mood(m, 20, t, 3.0)
        self.assertFalse(m.disco)

    def test_disco_hysteresis_and_fade(self):
        m = Mood()
        t = run_mood(m, 20, 0, 6.5)
        self.assertTrue(m.disco)
        t = run_mood(m, 12, t, 3.0)                 # below 15 but above 10: keep dancing
        self.assertTrue(m.disco)
        t = run_mood(m, 2, t, 1.0)                  # pause shorter than the cooldown
        self.assertTrue(m.disco)
        t = run_mood(m, 2, t, 0.7)
        self.assertFalse(m.disco)
        self.assertGreater(m.intensity, 0)          # fades out smoothly
        run_mood(m, 2, t, 2.0)
        self.assertEqual(m.intensity, 0)

    def test_disco_can_be_disabled(self):
        m = Mood()
        run_mood(m, 25, 0, 8, allowed=False)
        self.assertFalse(m.disco)
        self.assertEqual(m.state, "hyper")
        m2 = Mood()
        t = run_mood(m2, 25, 0, 6)
        m2.update(25, t + 0.05, disco_allowed=False)   # turned off mid-dance
        self.assertFalse(m2.disco)

    def test_hat_wiggle(self):
        h = HatWiggle()
        self.assertEqual(h.pose(), (0.0, 0.0))
        h.kick(1)
        angles = []
        for _ in range(10):
            h.step(0.033)
            angles.append(h.pose()[0])
        self.assertGreater(max(abs(a) for a in angles), 1.0)
        self.assertLessEqual(max(abs(a) for a in angles), 6.0)
        for _ in range(100):
            h.step(0.033)
        self.assertEqual(h.energy, 0.0)
        for _ in range(50):                 # very fast clicks: the energy is capped
            h.kick(5)
        self.assertLessEqual(h.energy, 1.0)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.lib = MacroLibrary(self.dir / "macros")

    def macro(self, n=2):
        return Macro(name="x", steps=[Step("click", i, i) for i in range(n)])

    def test_safe_name(self):
        self.assertFalse(set(safe_name('a/b:c*?<>|"')) & set('/\\:*?<>|"'))
        self.assertNotEqual(safe_name("CON").upper(), "CON")
        self.assertEqual(safe_name("   ", "Макрос"), "Макрос")
        self.assertLessEqual(len(safe_name("я" * 200)), 60)

    def test_crud(self):
        a = self.lib.create("Морковка", self.macro(3))
        self.assertEqual(a, "Морковка")
        b = self.lib.create("Морковка")
        self.assertEqual(b, "Морковка (2)")
        self.assertEqual(self.lib.names(), ["Морковка", "Морковка (2)"])
        self.assertEqual(len(self.lib.load("Морковка").steps), 3)

        m = self.lib.load(b)
        m.steps.append(Step("wait", delay_ms=10))
        self.lib.save(b, m)
        self.assertEqual(len(self.lib.load(b).steps), 1)
        self.assertFalse(list(self.lib.folder.glob("*.tmp")))

        c = self.lib.rename(b, "Шахта")
        self.assertEqual(c, "Шахта")
        self.assertFalse(self.lib.exists(b))
        self.assertEqual(self.lib.rename("Шахта", "Морковка"), "Морковка (2)")   # taken: a number is added
        self.assertEqual(self.lib.rename("Морковка (2)", "морковка (2)"), "морковка (2)")  # case only

        d = self.lib.duplicate("Морковка", "Морковка (копия)")
        self.assertEqual(len(self.lib.load(d).steps), 3)
        self.lib.delete("Морковка")
        self.assertNotIn("Морковка", self.lib.names())
        self.assertIn(d, self.lib.names())

    def test_import(self):
        src = self.dir / "outside.json"
        self.macro(4).save(src)
        name = self.lib.import_file(src)
        self.assertEqual(len(self.lib.load(name).steps), 4)
        self.assertTrue(src.exists())

    def test_migration(self):
        autosave = self.dir / "autosave_macro.json"
        self.macro(5).save(autosave)
        old = self.dir / "old"
        old.mkdir()
        self.macro(1).save(old / "Старый.json")
        (old / "битый.json").write_text("{not json", encoding="utf-8")
        added = self.lib.migrate(autosave, [old], autosave_name="Макрос 1")
        self.assertEqual(sorted(added), ["x", "Старый"])
        self.assertFalse(autosave.exists())
        self.assertTrue(autosave.with_suffix(".json.bak").exists())
        self.assertTrue((old / "Старый.json").exists())     # originals are not touched
        self.assertEqual(self.lib.migrate(autosave, [old]), [])   # a second time: nothing


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.played = []

    def play(self, path, volume, on_error=None, max_seconds=None):
        self.played.append((Path(path).name, round(volume, 3)))
        self.limits = getattr(self, "limits", []) + [max_seconds]

    def stop(self):
        self.stopped = getattr(self, "stopped", 0) + 1

    stop_all = stop


class SoundTests(unittest.TestCase):
    def test_defaults_exist_and_valid(self):
        for ev in EVENTS:
            self.assertTrue(check_wav(default_path(ev)), ev)

    def test_settings_persist(self):
        s = Settings()
        s.sound_volume, s.sound_tick, s.countdown_play = 35, False, True
        s.sound_custom = {"record_start": "C:/my/meow.wav", "bogus": "x", "tick": 5}
        s.anim_disco = False
        s.save()
        s2 = Settings.load()
        self.assertEqual((s2.sound_volume, s2.sound_tick, s2.countdown_play, s2.anim_disco), (35, False, True, False))
        self.assertEqual(s2.sound_custom, {"record_start": "C:/my/meow.wav"})

    def test_bad_settings_are_sanitised(self):
        path = Path(os.environ["KOTOCLICK_CONFIG_DIR"]) / "settings.json"
        path.write_text(json.dumps({"sound_volume": 900, "sound_custom": "nope", "current_tab": 7}), encoding="utf-8")
        s = Settings.load()
        self.assertEqual(s.sound_volume, 100)
        self.assertEqual(s.sound_custom, {})
        self.assertIn(s.current_tab, (0, 1, 2))

    def test_soundboard(self):
        s = Settings()
        fake = FakeBackend()
        sb = SoundBoard(s, fake)
        s.sound_volume = 50
        self.assertTrue(sb.play("record_start"))
        self.assertEqual(fake.played[-1], ("meow.wav", 0.5))
        sb.play("tick")
        self.assertEqual(fake.played[-1], ("tick.wav", 0.175))      # ticks are quieter
        s.sound_tick = False
        self.assertFalse(sb.play("tick"))
        self.assertTrue(sb.play("tick", preview=True))                # the play button always plays
        s.sound_custom = {"countdown": "/nope/missing.wav"}
        sb.play("countdown")
        self.assertEqual(fake.played[-1][0], "countdown.wav")             # no file: the default
        my = Path(tempfile.mkdtemp()) / "my.wav"
        my.write_bytes(Path(default_path("tick")).read_bytes())
        s.sound_custom = {"countdown": str(my)}
        sb.play("countdown")
        self.assertEqual(fake.played[-1][0], "my.wav")
        s.sound_volume = 0
        self.assertFalse(sb.play("countdown"))

    def test_scaled_wav(self):
        src = default_path("record_start")
        full = scaled_wav(src, 1.0)
        half = scaled_wav(src, 0.5)
        self.assertEqual(len(full), len(half))
        tmp = Path(tempfile.mkdtemp())
        peaks = []
        for data, name in ((full, "f.wav"), (half, "h.wav")):
            (tmp / name).write_bytes(data)
            with wave.open(str(tmp / name)) as w:
                raw = w.readframes(w.getnframes())
            peaks.append(max(abs(v) for v in struct.unpack(f"<{len(raw) // 2}h", raw)))
        self.assertAlmostEqual(peaks[1] / peaks[0], 0.5, delta=0.02)
        bad = tmp / "bad.wav"
        bad.write_bytes(b"ID3 not a wav")
        self.assertFalse(check_wav(str(bad)))


class PromoTests(unittest.TestCase):
    def test_interval_bounds_and_never_immediate(self):
        for seed in range(50):
            p = promo.PromoScheduler(1000.0, random.Random(seed))
            self.assertFalse(p.check(1000.0, False))
            self.assertGreaterEqual(p.due - 1000.0, 25 * 60)
            self.assertLessEqual(p.due - 1000.0, 35 * 60)

    def test_shows_once_then_reschedules(self):
        p = promo.PromoScheduler(0.0, random.Random(1))
        due = p.due
        self.assertFalse(p.check(due - 1, False))
        self.assertTrue(p.check(due, False))
        self.assertFalse(p.check(due + 1, False))
        self.assertGreaterEqual(p.due, due + 25 * 60)
        self.assertEqual(p.shown, 1)

    def test_postponed_while_busy(self):
        p = promo.PromoScheduler(0.0, random.Random(2))
        t = p.due
        for i in range(10):                 # clicking all the time: do not interrupt
            self.assertFalse(p.check(t + i * 10, True))
        self.assertFalse(p.check(t + 100, False))     # became free: wait a bit more
        self.assertTrue(p.check(t + 90 + promo.BUSY_RETRY, False))

    def test_url(self):
        self.assertEqual(promo.PROMO_URL, "https://t.me/DownGrabBot?start=KotoClick")


class WindowTests(unittest.TestCase):
    """Countdown before recording, the library and the bubble in the window."""

    @classmethod
    def setUpClass(cls):
        import main as app_main
        cls.app = app_main.create_app([])

    def setUp(self):
        from app.engine import Engine
        from app.hotkeys import HotkeyListener
        from app.ui.main_window import MainWindow
        from test_core import FakeMouse
        os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
        self.fake = FakeBackend()
        self.lib_dir = Path(tempfile.mkdtemp()) / "macros"
        self.engine = Engine(mouse_factory=FakeMouse)
        self.calls = []
        self.engine.start_recording = lambda *a, **kw: self.calls.append(a) or True
        self.engine.stop_recording = lambda **kw: [Step("click", 1, 2)]
        self.win = MainWindow(Settings(language="ru"), self.engine, HotkeyListener(),
                              sound_backend=self.fake, library_dir=self.lib_dir)

    def tearDown(self):
        self.win.close()

    def sounds(self):
        return [n for n, _ in self.fake.played]

    def test_record_countdown_beeps_then_meow(self):
        w = self.win
        w.on_hotkey("f7")
        self.assertEqual(w.state, "countdown")
        self.assertEqual(w.status_title.text().replace("\xa0", " "), "Мышка готовится… 3")
        for _ in range(3):
            w._countdown_tick()
        self.assertEqual(w.state, "recording")
        self.assertEqual(len(self.calls), 1)
        # one file for the whole countdown (beep, beep, beep), then the "meow"
        self.assertEqual(self.sounds(), ["countdown.wav", "meow.wav"])
        self.assertTrue(w._tick_timer.isActive())
        w.on_hotkey("f7")
        self.assertEqual(w.state, "idle")
        self.assertFalse(w._tick_timer.isActive())
        self.assertEqual(self.sounds()[-1], "record_stop.wav")

    def test_countdown_cancel_by_panic_and_f7(self):
        w = self.win
        for cancel in ("esc", "f9", "f7"):
            w.on_hotkey("f7")
            self.assertEqual(w.state, "countdown")
            w._countdown_tick()
            w.on_hotkey(cancel)
            self.assertEqual(w.state, "idle", cancel)
            self.assertFalse(w._countdown_timer.isActive())
        self.assertEqual(self.calls, [])

    def test_countdown_can_be_turned_off(self):
        w = self.win
        w.cd_record.setChecked(False)
        w.on_hotkey("f7")
        self.assertEqual(w.state, "recording")
        w.on_hotkey("f7")

    def test_play_hotkey_countdown_optional(self):
        w = self.win
        w.macro.steps = [Step("wait", delay_ms=10000)]
        w.on_hotkey("f8")
        self.assertEqual(w.state, "playing")
        self.assertEqual(self.sounds()[-1], "play_start.wav")
        w.on_hotkey("esc")
        w.cd_play.setChecked(True)
        w.on_hotkey("f8")
        self.assertEqual(w.state, "countdown")
        w.on_hotkey("esc")
        self.assertEqual(w.state, "idle")

    def test_library_in_window(self):
        w = self.win
        self.assertEqual(w.macro_combo.count(), 1)          # empty library: one new macro
        first = w.current_macro
        w.macro.steps = [Step("click", 5, 5)]
        w._fill_table()                                     # edit -> autosave
        w._flush_macro()
        self.assertEqual(len(w.library.load(first).steps), 1)
        w._new_macro()
        self.assertEqual(w.macro_combo.count(), 2)
        self.assertEqual(w.macro.steps, [])
        self.assertEqual(w.settings.current_macro, w.current_macro)
        w._switch_macro(first)
        self.assertEqual(len(w.macro.steps), 1)
        w._duplicate_macro()
        self.assertEqual(w.macro_combo.count(), 3)
        w._ask = lambda text: True
        w._delete_macro()
        self.assertEqual(w.macro_combo.count(), 2)

    def test_reaction_switches(self):
        w = self.win
        w.anim_disco.setChecked(False)
        self.assertFalse(w.cat.anim_disco)
        w.anim_master.setChecked(False)
        self.assertFalse(w.anim_hat.isEnabled())
        self.assertFalse(w.cat.anim_enabled)
        self.assertFalse(w.settings.anim_enabled)

    def test_promo_toast_does_not_open_link_by_itself(self):
        w = self.win
        w.show()
        w.show_promo()
        self.assertTrue(w.promo_toast.isVisible())
        self.assertIn("https://t.me/DownGrabBot?start=KotoClick", w.promo_toast.label.text().replace("\xa0", " "))
        self.assertIn("ТГ бот", w.promo_toast.label.text().replace("\xa0", " "))
        self.assertEqual(w.promo_toast.opened_links, 0)
        self.assertFalse(w.promo_toast.label.openExternalLinks())
        w.set_state("clicking")                              # busy: the bubble hides
        self.app.processEvents()
        w.engine.stop_all()
        w.set_state("idle")


if __name__ == "__main__":
    unittest.main()
