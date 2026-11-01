"""Round five: easter egg, non-breaking spaces, a single countdown sound, animations,
sound trimming, configurable hotkeys and the first-run language."""
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["KOTOCLICK_SOUND"] = "off"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from kotoclick import i18n, paths, sound_trim, sounds  # noqa: E402
from kotoclick.promo import EGG_COOLDOWN, EasterEgg, PromoScheduler  # noqa: E402
from kotoclick.settings import HOTKEY_DEFAULTS, Settings  # noqa: E402
from kotoclick.typography import NBSP, nbsp, tooltip_html  # noqa: E402

TMP = Path(tempfile.mkdtemp())


def make_wav(path, seconds=2.0, rate=22050, channels=1, freq=440):
    n = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            v = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", v) * channels
        w.writeframes(bytes(frames))
    return str(path)


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.played, self.limits, self.stopped = [], [], 0

    def play(self, path, volume, on_error=None, max_seconds=None):
        self.played.append(Path(path).name)
        self.limits.append(max_seconds)

    def stop(self):
        self.stopped += 1

    stop_all = stop


# ---------------------------------------------------------------- logic without a window
class EasterEggTests(unittest.TestCase):
    def test_ten_quick_clicks_then_cooldown(self):
        egg = EasterEgg()
        t = 100.0
        hits = [egg.click(t + i * 0.5) for i in range(10)]
        self.assertEqual(hits, [False] * 9 + [True])
        t2 = t + 30
        self.assertFalse(any(egg.click(t2 + i * 0.3) for i in range(10)))      # spam: stays quiet
        t3 = t + EGG_COOLDOWN + 5
        self.assertTrue([egg.click(t3 + i * 0.3) for i in range(10)][-1])        # after 10 minutes: again

    def test_slow_clicks_do_not_count(self):
        egg = EasterEgg()
        self.assertFalse(any(egg.click(i * 2.5) for i in range(30)))           # gap > 2 s: count restarts

    def test_postpone_moves_schedule(self):
        p = PromoScheduler(0.0)
        p.postpone(1000.0)
        self.assertGreaterEqual(p.due, 1000.0 + 25 * 60)
        due = p.due
        p.postpone(1001.0)                     # never earlier than already scheduled
        self.assertGreaterEqual(p.due, due)


class TypographyTests(unittest.TestCase):
    def test_short_words_glued(self):
        self.assertEqual(nbsp("Я сижу в коробке и жду", tail=False),
                         f"Я{NBSP}сижу в{NBSP}коробке и{NBSP}жду")
        out = nbsp("I want to go on a walk", tail=False)
        for pair in ("I\u00a0want", "to\u00a0go", "on\u00a0a\u00a0walk"):
            self.assertIn(pair, out)

    def test_dash_and_tail(self):
        out = nbsp("Котик спит — не буди его сегодня")
        self.assertIn(f"спит{NBSP}—", out)
        self.assertTrue(out.endswith(f"его{NBSP}сегодня"))      # the last word is not left alone

    def test_tags_untouched_and_idempotent(self):
        html = 'А у меня есть <a href="https://t.me/DownGrabBot?start=KotoClick">ТГ бот</a> для скачивания видео!'
        out = nbsp(html)
        self.assertIn('<a href="https://t.me/DownGrabBot?start=KotoClick">', out)
        self.assertEqual(nbsp(out), out)
        self.assertEqual(out.replace(NBSP, " "), html)            # only spaces change

    def test_tooltip_is_multiline(self):
        tip = tooltip_html(i18n.STRINGS["ru"]["badge_tip"])
        self.assertIn("<br>", tip)
        for line in tip.split("<br>"):
            plain = line.replace("<p style='white-space:pre'>", "").replace("</p>", "")
            self.assertLessEqual(len(plain), 48)


class LanguageDetectTests(unittest.TestCase):
    def test_tags(self):
        cases = {"ru_RU": "ru", "ru-RU": "ru", "uk_UA": "ru", "be_BY": "ru", "en_US": "en",
                 "de_DE": "en", "Russian_Russia": "ru"}
        for tag, want in cases.items():
            self.assertEqual(i18n.detect_language([tag]), want, tag)

    def test_empty_falls_back(self):
        self.assertEqual(i18n.detect_language([]), "en")
        self.assertEqual(i18n.detect_language([None, "", "C", "POSIX"]), "en")
        self.assertEqual(i18n.detect_language([None, "C", "ru_RU.UTF-8"]), "ru")

    def test_system_tags_mocked(self):
        with mock.patch.object(i18n, "system_language_tags", return_value=["de-DE", "de_DE"]):
            self.assertEqual(i18n.detect_language(), "en")
        with mock.patch.object(i18n, "system_language_tags", return_value=["ru-RU"]):
            self.assertEqual(i18n.detect_language(), "ru")

    def test_settings_language_auto(self):
        self.assertEqual(Settings().language, "")
        self.assertEqual(Settings(language="xx").validate().language, "")
        self.assertEqual(Settings(language="en").validate().language, "en")


class HotkeySettingsTests(unittest.TestCase):
    def test_defaults_and_old_file_migration(self):
        p = TMP / "old_settings.json"
        p.write_text(json.dumps({"hotkey_click": "f6", "hotkey_record": "f7", "hotkey_play": "f8",
                                 "hotkey_panic": "f9", "language": "ru"}), encoding="utf-8")
        s = Settings.load(p)
        self.assertEqual(s.hotkey_stop, "esc")                    # Esc used to be "hard-wired"
        self.assertEqual(s.language, "ru")                        # a manual choice is not touched
        self.assertEqual(set(HOTKEY_DEFAULTS), {"hotkey_click", "hotkey_record", "hotkey_play",
                                                "hotkey_panic", "hotkey_stop"})

    def test_duplicates_fixed(self):
        s = Settings(hotkey_click="f9", hotkey_panic="f9").validate()
        keys = [getattr(s, f) for f in HOTKEY_DEFAULTS if getattr(s, f)]
        self.assertEqual(len(keys), len(set(keys)))

    def test_stop_key_can_be_empty(self):
        self.assertEqual(Settings(hotkey_stop="").validate().hotkey_stop, "")


class TrimTests(unittest.TestCase):
    def test_wav_trim_and_save(self):
        src = make_wav(TMP / "long tone.wav", seconds=4.0, channels=2)
        pcm = sound_trim.load_pcm(src)
        self.assertEqual(pcm.channels, 2)
        self.assertAlmostEqual(pcm.duration, 4.0, places=2)
        out = sound_trim.save_trimmed(pcm, 0.5, 2.0, TMP / "sc", "record_start", src)
        self.assertTrue(out.name.startswith("record_start_"))
        with wave.open(str(out)) as w:
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 1.5, places=2)
            frames = w.readframes(w.getnframes())
        first = struct.unpack("<h", frames[:2])[0]
        self.assertLessEqual(abs(first), 50)                       # smooth start without a click
        self.assertEqual(sounds.check_sound(str(out)), "")

    def test_too_short_and_bad_file(self):
        pcm = sound_trim.load_pcm(make_wav(TMP / "s.wav", seconds=1.0))
        with self.assertRaises(sound_trim.TrimError):
            sound_trim.save_trimmed(pcm, 0.5, 0.51, TMP / "sc", "tick", "s.wav")
        bad = TMP / "bad.mp3"
        bad.write_bytes(b"\xff\xfb" + b"\x00" * 200)
        with self.assertRaises(sound_trim.TrimError):
            sound_trim.load_pcm(str(bad))

    def test_peaks(self):
        pcm = sound_trim.load_pcm(make_wav(TMP / "p.wav", seconds=1.0))
        pk = sound_trim.peaks(pcm, 50)
        self.assertEqual(len(pk), 50)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in pk))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg нужен только тесту, чтобы сделать mp3")
    def test_mp3_decoded_by_qt(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        src = make_wav(TMP / "for_mp3.wav", seconds=3.0)
        mp3 = TMP / "song.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, str(mp3)], check=True)
        pcm = sound_trim.load_pcm(str(mp3))
        self.assertGreater(pcm.duration, 2.8)
        out = sound_trim.save_trimmed(pcm, 0.0, 1.0, TMP / "sc", "countdown", str(mp3))
        self.assertEqual(out.suffix, ".wav")


class CountdownSoundTests(unittest.TestCase):
    def test_single_file_three_seconds(self):
        p = Path(sounds.default_path("countdown"))
        self.assertEqual(p.name, "countdown.wav")
        with wave.open(str(p)) as w:
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 3.0, places=1)
        self.assertFalse((p.parent / "beep.wav").exists())
        self.assertEqual(sounds.max_seconds_for("countdown"), 3.0)

    def test_custom_countdown_is_capped(self):
        s = Settings()
        wav, media = FakeBackend(), FakeBackend()
        sb = sounds.SoundBoard(s, wav, media=media)
        s.sound_custom = {"countdown": make_wav(TMP / "long_cd.wav", seconds=6.0)}
        sb.play("countdown")
        self.assertEqual(wav.limits[-1], 3.0)
        sb.stop()
        self.assertEqual(wav.stopped, 1)
        self.assertEqual(media.stopped, 1)


# ---------------------------------------------------------------- window
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main as app_main
        cls.app = app_main.create_app([])

    def make(self, **kw):
        from kotoclick.engine import Engine
        from kotoclick.hotkeys import HotkeyListener
        from kotoclick.ui.main_window import MainWindow
        from test_core import FakeMouse
        os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
        self.wav, self.media = FakeBackend(), FakeBackend()
        self.engine = Engine(mouse_factory=FakeMouse)
        kw.setdefault("language", "ru")
        w = MainWindow(Settings(**kw), self.engine, HotkeyListener(), sound_backend=self.wav,
                       sound_media=self.media, library_dir=Path(tempfile.mkdtemp()) / "m")
        self.addCleanup(w.close)
        return w

    # --- 3: countdown ---
    def test_countdown_plays_once_and_cancel_stops(self):
        w = self.make()
        w._start_countdown(lambda: None)
        w._countdown_tick()
        w._countdown_tick()
        self.assertEqual(self.wav.played, ["countdown.wav"])
        self.assertEqual(self.wav.limits, [3.0])
        w._cancel_countdown()
        self.assertGreaterEqual(self.wav.stopped, 1)
        self.assertEqual(w.state, "idle")

    # --- 1: easter egg ---
    def test_easter_egg_shows_promo_once(self):
        w = self.make()
        shown = []
        w.show_promo = lambda: shown.append(1)
        clock = [5000.0]
        with mock.patch("kotoclick.ui.main_window.time.monotonic", side_effect=lambda: clock[0]):
            for _ in range(10):
                clock[0] += 0.4
                w._on_cat_clicked()
            self.assertEqual(shown, [1])
            self.assertGreaterEqual(w.promo.due, clock[0] + 25 * 60)     # the scheduled one does not come right after
            for _ in range(20):
                clock[0] += 0.4
                w._on_cat_clicked()
            self.assertEqual(shown, [1])                                 # spamming does not help
        self.assertIn("t.me/DownGrabBot?start=KotoClick", w.promo_toast.label.text())

    def test_easter_egg_not_while_busy(self):
        w = self.make()
        shown = []
        w.show_promo = lambda: shown.append(1)
        w.state = "clicking"
        for _ in range(10):
            w._on_cat_clicked()
        self.assertEqual(shown, [])
        self.assertIsNone(w.egg.last_shown)

    # --- 7: animations ---
    def test_anim_off_stops_everything(self):
        w = self.make(anim_enabled=False)
        self.assertFalse(w.cat.animating)
        self.assertFalse(w.mouse_mascot.animating)
        self.assertFalse(w.anim_hat.isEnabled())
        self.assertFalse(w.anim_disco.isEnabled())
        self.assertFalse(w.promo_toast.animated)
        w.set_state("clicking")
        w.cat.poke()
        self.assertFalse(w.cat.animating)
        self.assertNotEqual(w.paw._anim.state(), w.paw._anim.State.Running)
        self.assertEqual(w.cat.disco_level, 0.0)
        self.assertEqual(w.cat.hat_pose(), (0.0, 0.0))
        w.cat._tick()                                  # even a stray frame starts nothing
        self.assertEqual(w.cat.mood.state, "calm")
        self.assertIsNone(w.status_lore.graphicsEffect())
        w.state = "idle"

    def test_anim_on_again_and_subtoggles(self):
        w = self.make(anim_enabled=False)
        w.anim_master.setChecked(True)
        self.assertTrue(w.cat.animating)
        self.assertTrue(w.mouse_mascot.animating)
        self.assertTrue(w.anim_hat.isEnabled() and w.anim_disco.isEnabled())
        w.anim_disco.setChecked(False)
        self.assertFalse(w.cat.anim_disco)
        w.anim_master.setChecked(False)
        self.assertFalse(w.cat.animating)

    # --- 10: hotkeys ---
    def test_clear_esc_makes_it_recordable(self):
        w = self.make()
        self.assertIn("esc", w._app_keys())
        w._clear_stop_key()
        self.assertEqual(w.settings.hotkey_stop, "")
        self.assertNotIn("esc", w._app_keys())
        got = {}
        self.engine.start_recording = lambda *a, **kw: got.update(kw) or False
        w.toggle_recording() if hasattr(w, "toggle_recording") else None
        if got:
            self.assertNotIn("esc", set(got["excluded_keys"]))
        self.engine._rec_excluded = {k for k in w._app_keys() if k}
        self.assertNotIn("esc", self.engine._rec_excluded)
        self.assertIn("f9", self.engine._rec_excluded)

    def test_reassign_conflict_and_reset(self):
        w = self.make()
        btn = next(b for b, f in w.hk_buttons.items() if f == "hotkey_stop")
        w._begin_capture(btn)
        w.on_key_captured("f6")                               # already taken by auto-click
        self.assertEqual(w.settings.hotkey_stop, "esc")
        w._begin_capture(btn)
        w.on_key_captured("pause")
        self.assertEqual(w.settings.hotkey_stop, "pause")
        click_btn = next(b for b, f in w.hk_buttons.items() if f == "hotkey_click")
        w._begin_capture(click_btn)
        w.on_key_captured("f2")
        self.assertEqual(w.settings.hotkey_click, "f2")
        self.assertEqual(w.key_click.key_name, "f2")           # the button on the tab was updated too
        self.assertIn("F2", w.status_title.text() + w.status_lore.text() + w.paw.caption + self._footer(w))
        panics = []
        w.panic = lambda: panics.append(1)
        w.on_hotkey("pause")
        w.on_hotkey("esc")                                     # Esc is no longer a stop key
        self.assertEqual(panics, [1])
        w._reset_keys()
        self.assertEqual({f: getattr(w.settings, f) for f in HOTKEY_DEFAULTS}, HOTKEY_DEFAULTS)

    def _footer(self, w):
        from PySide6.QtWidgets import QLabel
        return " ".join(lb.text() for lb in w.findChildren(QLabel))

    def test_esc_in_other_slot_cancels_capture(self):
        w = self.make()
        w._begin_capture(w.key_click)
        w.on_key_captured("esc")
        self.assertEqual(w.settings.hotkey_click, "f6")

    # --- 6: header badge ---
    def test_badge(self):
        from PySide6.QtWidgets import QLabel
        w = self.make()
        texts = [lb for lb in w.findChildren(QLabel) if lb.text() == i18n.tr("badge")]
        self.assertEqual(i18n.STRINGS["ru"]["badge"], "офлайн · без интернета")
        self.assertEqual(i18n.STRINGS["en"]["badge"], "offline · no internet")
        self.assertTrue(texts)
        tip = texts[0].toolTip()
        self.assertIn("<br>", tip)
        self.assertNotIn("t.me", tip)
        self.assertNotIn("Telegram", tip)

    # --- 9: trimming from the window ---
    def test_offer_trim_choices(self):
        w = self.make()
        src = make_wav(TMP / "pick.wav", seconds=5.0)
        for choice, check in (("save", lambda r: Path(r).parent == paths.sounds_custom_dir()),
                              ("nocut", lambda r: r == src),
                              (None, lambda r: r == "")):
            def run(dlg, c=choice):
                self.assertEqual(dlg.max_seconds, 3.0)
                dlg.set_range(1.0, 2.5)
                dlg.choice = c
            w._run_trim_dialog = run
            res = w._offer_trim("countdown", src)
            self.assertTrue(check(res), (choice, res))
            if choice == "save":
                self.assertAlmostEqual(sound_trim.load_pcm(res).duration, 1.5, places=2)

    def test_offer_trim_unreadable_uses_original(self):
        w = self.make()
        bad = TMP / "weird.mp3"
        bad.write_bytes(b"\xff\xfb" + b"\x00" * 300)
        w._run_trim_dialog = lambda dlg: self.fail("окно не должно открываться")
        self.assertEqual(w._offer_trim("tick", str(bad)), str(bad))

    def test_trim_dialog_widgets(self):
        from kotoclick.ui.trim_dialog import TrimDialog
        src = make_wav(TMP / "dlg.wav", seconds=8.0)
        pcm = sound_trim.load_pcm(src)
        d = TrimDialog(src, pcm, "Мяу", 5.0, volume=0.5)
        self.addCleanup(d.deleteLater)
        self.assertAlmostEqual(d.end - d.start, 5.0, places=2)    # by default not longer than the limit
        d.set_range(2.0, 3.0)
        self.assertAlmostEqual(d.start, 2.0, places=2)
        self.assertAlmostEqual(d.end, 3.0, places=2)


class FirstRunLanguageTests(unittest.TestCase):
    """A live start without a settings file with different LC_ALL values (offscreen)."""

    def run_with(self, lc):
        cfg = tempfile.mkdtemp()
        code = ("import os,sys; sys.path.insert(0, %r); import main as m; from kotoclick import i18n;"
                "from kotoclick.settings import Settings;"
                "app = m.create_app([]);"
                "from kotoclick.ui.main_window import MainWindow;"
                "from kotoclick.engine import Engine; from kotoclick.hotkeys import HotkeyListener;"
                "s = Settings.load();"
                "w = MainWindow(s, Engine(), HotkeyListener(), library_dir=os.path.join(%r,'m'));"
                "print('LANG=' + i18n.language()); print('TAB=' + w.windowTitle())"
                ) % (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), cfg)
        env = dict(os.environ, LC_ALL=lc, LANG=lc, LANGUAGE="", KOTOCLICK_CONFIG_DIR=cfg,
                   QT_QPA_PLATFORM="offscreen", KOTOCLICK_SOUND="off")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return [ln for ln in r.stdout.splitlines() if ln.startswith("LANG=")][0][5:]

    def test_ru_and_en_locales(self):
        self.assertEqual(self.run_with("ru_RU.UTF-8"), "ru")
        self.assertEqual(self.run_with("en_US.UTF-8"), "en")
        self.assertEqual(self.run_with("de_DE.UTF-8"), "en")


if __name__ == "__main__":
    unittest.main()
