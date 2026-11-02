"""Custom MP3/OGG/M4A sounds (QMediaPlayer) and the "Chatty cat" phrases."""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["KOTOCLICK_SOUND"] = "off"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import i18n, phrases, sounds  # noqa: E402
from app.phrases import (PHRASES, PhrasePicker, fields, greeting_situation,  # noqa: E402
                              milestone_reached)
from app.settings import Settings  # noqa: E402
from app.sounds import SoundBoard, check_sound, default_path  # noqa: E402

TMP = Path(tempfile.mkdtemp())


def make_file(name, data=b"\xff\xfb" + b"\x00" * 400):
    p = TMP / name
    p.write_bytes(data)
    return str(p)


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.played = []
        self.errors = {}          # path -> error text the player will "return"
        self.limits = []
        self.stopped = 0

    def play(self, path, volume, on_error=None, max_seconds=None):
        self.played.append((Path(path).name, round(volume, 3)))
        self.limits.append(max_seconds)
        if path in self.errors and on_error:
            on_error(self.errors[path])

    def stop(self):
        self.stopped += 1

    stop_all = stop


class SoundFormatTests(unittest.TestCase):
    def test_check_sound(self):
        wav = make_file("ok.wav", Path(default_path("tick")).read_bytes())
        self.assertEqual(check_sound(wav), "")
        mp3 = make_file("song.mp3")
        self.assertEqual(check_sound(mp3), "" if sounds.media_supported() else "no_media")
        self.assertEqual(check_sound(make_file("notes.txt", b"hello")), "bad_format")
        self.assertEqual(check_sound(make_file("empty.mp3", b"")), "bad_format")
        self.assertEqual(check_sound(str(TMP / "missing.mp3")), "bad_format")
        for ext in (".MP3", ".ogg", ".m4a"):
            self.assertIn(ext.lower(), sounds.SOUND_EXTS)

    def test_routing_wav_vs_mp3(self):
        s = Settings()
        s.sound_volume = 50
        wav_out, media = FakeBackend(), FakeBackend()
        sb = SoundBoard(s, wav_out, media=media)
        mp3 = make_file("meow.mp3")
        s.sound_custom = {"record_start": mp3}
        sb.play("record_start")
        self.assertEqual(media.played, [("meow.mp3", 0.5)])        # master volume
        self.assertEqual(wav_out.played, [])
        sb.play("countdown")                                         # the default goes through WAV
        self.assertEqual(wav_out.played[-1][0], "countdown.wav")
        wav = make_file("my.wav", Path(default_path("tick")).read_bytes())
        s.sound_custom = {"record_start": wav}
        sb.play("record_start")
        self.assertEqual(wav_out.played[-1][0], "my.wav")
        self.assertEqual(len(media.played), 1)

    def test_decode_error_falls_back_and_reports_once(self):
        s = Settings()
        wav_out, media = FakeBackend(), FakeBackend()
        reported = []
        sb = SoundBoard(s, wav_out, media=media, on_error=lambda *a: reported.append(a))
        bad = make_file("broken.mp3", b"not really an mp3 at all")
        media.errors[bad] = "Could not open file"
        s.sound_custom = {"record_start": bad}
        sb.play("record_start")
        self.assertEqual(wav_out.played[-1][0], "meow.wav")          # the default right away
        self.assertEqual(reported, [("record_start", bad, "Could not open file")])
        self.assertIn(bad, sb.broken)
        sb.play("record_start")                                      # do not torture the broken file any more
        self.assertEqual(len(media.played), 1)
        self.assertEqual(wav_out.played[-1][0], "meow.wav")
        self.assertEqual(len(reported), 1)
        sb.forget(bad)                                               # picked again: another try
        sb.play("record_start")
        self.assertEqual(len(media.played), 2)

    def test_no_qtmultimedia_falls_back(self):
        s = Settings()
        wav_out = FakeBackend()
        reported = []
        orig = sounds.auto_media_backend
        sounds.auto_media_backend = lambda: None
        try:
            sb = SoundBoard(s, wav_out, on_error=lambda *a: reported.append(a[2]))
            s.sound_custom = {"play_start": make_file("start.ogg")}
            self.assertTrue(sb.play("play_start"))
        finally:
            sounds.auto_media_backend = orig
        self.assertEqual(wav_out.played[-1][0], "play_start.wav")
        self.assertEqual(reported, ["no_media"])

    def test_muted_plays_nothing(self):
        s = Settings()
        s.sound_volume = 0
        media = FakeBackend()
        sb = SoundBoard(s, FakeBackend(), media=media)
        s.sound_custom = {"tick": make_file("t.mp3")}
        self.assertFalse(sb.play("tick", preview=True))
        self.assertEqual(media.played, [])


@unittest.skipUnless(sounds.media_supported() and shutil.which("ffmpeg"), "нужны QtMultimedia и ffmpeg")
class RealMediaTests(unittest.TestCase):
    """A real QMediaPlayer (Qt's FFmpeg backend). There may be no sound card, so we check
    decoding, cutting by timer and errors, not that the sound is audible."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication
        cls.app = QCoreApplication.instance() or QApplication([])
        cls.mp3 = str(TMP / "long.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=6", cls.mp3], check=True)

    def spin(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)

    def test_plays_and_is_cut_off(self):
        b = sounds.QtMediaBackend(max_seconds=0.5)
        errors = []
        b.play(self.mp3, 0.3, on_error=errors.append)
        self.spin(0.3)
        slot = next(iter(b._slots.values()))
        self.assertAlmostEqual(slot.output.volume(), 0.3, places=2)
        self.spin(0.8)
        from PySide6.QtMultimedia import QMediaPlayer
        self.assertEqual(slot.player.playbackState(), QMediaPlayer.StoppedState)   # cut by the timer
        self.assertEqual(errors, [])
        b.stop_all()

    def test_bad_file_reports_error(self):
        b = sounds.QtMediaBackend(max_seconds=0.5)
        bad = make_file("garbage.mp3", os.urandom(4000))
        errors = []
        b.play(bad, 0.5, on_error=errors.append)
        self.spin(1.0)
        self.assertEqual(len(errors), 1)
        b.play(bad, 0.5, on_error=errors.append)      # second time: an error right away, no new player
        self.assertEqual(len(errors), 2)


class PhraseBankTests(unittest.TestCase):
    def test_every_situation_has_enough_phrases(self):
        for situation, bank in PHRASES.items():
            for lang in i18n.LANGUAGES:
                self.assertGreaterEqual(len(bank[lang]), phrases.MIN_PER_SITUATION, (situation, lang))
                self.assertEqual(len(set(bank[lang])), len(bank[lang]), f"повтор в {situation}/{lang}")

    def test_required_situations(self):
        need = {"greet_morning", "greet_day", "greet_evening", "greet_night", "idle", "click_countdown",
                "click_start", "clicking", "lively", "hyper", "disco", "click_stop", "milestone",
                "record_countdown", "record_start", "recording", "record_done", "play_start", "play_loop",
                "play_done", "play_stop", "panic", "hotkey_set", "macro_created", "macro_saved",
                "macro_deleted", "lang_switched", "sound_muted", "error", "no_hotkeys"}
        self.assertEqual(set(PHRASES), need)

    def test_placeholders_and_language(self):
        cyr = re.compile("[а-яё]", re.I)
        for situation, bank in PHRASES.items():
            for lang, items in bank.items():
                for p in items:
                    f = fields(p)
                    self.assertLessEqual(f, {"n", "w", "key"}, p)
                    if "w" in f:
                        self.assertIn("n", f, p)
                    p.format(n="1", w="x", key="F6")          # curly braces are not broken
                    self.assertLessEqual(len(p.format(n="1 000 000", w="кликов", key="Caps Lock")), 80, p)
                    if lang == "ru":
                        self.assertTrue(cyr.search(p), p)
                    else:
                        self.assertFalse(cyr.search(p), p)
        # where a number is needed there are also phrases without one, otherwise nothing to say without a counter
        for situation in ("click_stop", "hotkey_set"):
            for lang in i18n.LANGUAGES:
                self.assertTrue(any(not fields(p) for p in PHRASES[situation][lang]), situation)

    def test_picker_never_repeats(self):
        picker = PhrasePicker(rng=random.Random(5))
        for situation in PHRASES:
            for lang in i18n.LANGUAGES:
                prev = None
                for _ in range(60):
                    cur = picker.pick(situation, lang, n="7", w="w", key="F6")
                    self.assertTrue(cur)
                    self.assertNotEqual(cur, prev)
                    prev = cur

    def test_picker_filters_by_fields(self):
        picker = PhrasePicker(rng=random.Random(1))
        for _ in range(40):
            self.assertNotIn("{", picker.pick("click_stop", "ru"))
        seen = {picker.pick("click_stop", "ru", n="5", w="кликов") for _ in range(80)}
        self.assertTrue(any("5 кликов" in t for t in seen))
        self.assertEqual(picker.pick("nope", "ru"), "")

    def test_single_option_is_allowed_to_repeat(self):
        picker = PhrasePicker({"x": {"ru": ["один"]}})
        self.assertEqual([picker.pick("x", "ru") for _ in range(3)], ["один"] * 3)

    def test_greeting_and_milestones(self):
        self.assertEqual([greeting_situation(h) for h in (5, 10, 11, 16, 17, 22, 23, 0, 4)],
                         ["greet_morning"] * 2 + ["greet_day"] * 2 + ["greet_evening"] * 2 + ["greet_night"] * 3)
        self.assertEqual(milestone_reached(99, 0), 0)
        self.assertEqual(milestone_reached(100, 0), 100)
        self.assertEqual(milestone_reached(150, 100), 0)
        self.assertEqual(milestone_reached(2500, 100), 1000)
        self.assertEqual(milestone_reached(12_000, 0), 10_000)

    def test_lap_plural(self):
        i18n.set_language("ru")
        self.assertEqual([i18n.plural(n, "lap") for n in (1, 3, 10)], ["круг", "круга", "кругов"])
        i18n.set_language("en")
        self.assertEqual([i18n.plural(n, "lap") for n in (1, 3)], ["lap", "laps"])
        i18n.set_language("ru")


class ChattyWindowTests(unittest.TestCase):
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
        self.wav, self.media = FakeBackend(), FakeBackend()
        self.engine = Engine(mouse_factory=FakeMouse)
        self.engine.start_clicking = lambda *a, **kw: True
        self.engine.stop_all = lambda: None
        self.win = MainWindow(Settings(language="ru"), self.engine, HotkeyListener(), sound_backend=self.wav,
                              sound_media=self.media, library_dir=Path(tempfile.mkdtemp()) / "m")

    def tearDown(self):
        self.win.close()

    def bank(self, situation, lang="ru"):
        return PHRASES[situation][lang]

    def said(self, situation, lang="ru"):
        """The bubble text is one of the situation's phrases (with any placeholders)."""
        text = self.win.status_lore.text().replace("\xa0", " ")
        for p in self.bank(situation, lang):
            pat = re.escape(p).replace(r"\{n\}", ".+").replace(r"\{w\}", ".+").replace(r"\{key\}", ".+")
            if re.fullmatch(pat, text):
                return True
        return False

    def test_greeting_on_start(self):
        from datetime import datetime
        self.assertTrue(self.said(greeting_situation(datetime.now().hour)), self.win.status_lore.text().replace("\xa0", " "))

    def test_chatty_off_falls_back_to_plain_text(self):
        w = self.win
        w.chatty.setChecked(False)
        self.assertFalse(w.settings.chatty)
        self.assertEqual(w.status_lore.text().replace("\xa0", " "), i18n.tr("st_idle_lore", click="F6"))
        self.assertFalse(w._chat_timer.isActive())
        w._say("idle")
        self.assertEqual(w.status_lore.text().replace("\xa0", " "), i18n.tr("st_idle_lore", click="F6"))
        w.chatty.setChecked(True)
        self.assertTrue(w._chat_timer.isActive())

    def test_flash_beats_phrase(self):
        w = self.win
        w.flash("Важное сообщение")
        w._say("idle")
        self.assertEqual(w.status_lore.text().replace("\xa0", " "), "Важное сообщение")
        w._clear_flash()
        self.assertTrue(self.said("idle"))

    def test_click_session_phrases(self):
        w = self.win
        w.on_hotkey("f6")
        self.assertEqual(w.state, "clicking")
        self.assertTrue(self.said("click_start"))
        self.engine.clicks = 150
        w._update_counter()
        self.assertTrue(self.said("milestone"), w.status_lore.text().replace("\xa0", " "))
        w._update_counter()
        w.on_hotkey("f6")                       # stop by key -> the worker reports the stop
        w._on_worker_stopped()
        self.assertEqual(w.state, "idle")
        self.assertTrue(self.said("click_stop"))
        w.on_hotkey("f6")
        w.on_hotkey("esc")
        self.assertTrue(self.said("panic"))

    def test_moods(self):
        w = self.win
        w.on_hotkey("f6")
        w.cat.mood.state = "hyper"
        w._on_mood("hyper")
        self.assertTrue(self.said("hyper"))
        w.cat.mood.state = "calm"
        w._on_mood("calm")
        self.assertTrue(self.said("clicking"))

    def test_macro_loops_and_language(self):
        from app.macro import Step
        w = self.win
        self.engine.start_playback = lambda *a, **kw: True
        w.macro.steps = [Step("click", 1, 1)]
        w.on_hotkey("f8")
        self.assertTrue(self.said("play_start"))
        w._on_progress(0, 1)
        self.assertTrue(self.said("play_loop"))
        before = w.status_lore.text().replace("\xa0", " ")
        w._on_progress(0, 2)                    # 2nd loop: stay quiet
        self.assertEqual(w.status_lore.text().replace("\xa0", " "), before)
        w._on_worker_stopped()
        self.assertTrue(self.said("play_done"))
        w.set_language("en")
        self.assertTrue(self.said("lang_switched", "en"))
        w.volume.setValue(0)
        self.assertTrue(self.said("sound_muted", "en"))
        w.set_language("ru")

    def test_idle_rotation_only_when_visible(self):
        w = self.win
        w._chat_tick()                          # window not shown: wait
        self.assertEqual(w._chat_timer.interval(), 5000)
        w.show()
        self.app.processEvents()
        old = w.status_lore.text().replace("\xa0", " ")
        w._chat_tick()
        self.assertTrue(self.said("idle"))
        self.assertNotEqual(w.status_lore.text().replace("\xa0", " "), old)
        self.assertGreaterEqual(w._chat_timer.interval(), 40_000)

    def test_hotkeys_failed_and_engine_error(self):
        w = self.win
        w.on_hotkeys_failed("Не удалось запустить клавиши")
        self.assertEqual(w.status_lore.text().replace("\xa0", " "), "Не удалось запустить клавиши")   # the reason first
        w._clear_flash()
        self.assertTrue(self.said("no_hotkeys"))

    def test_pick_mp3_and_error_message(self):
        from PySide6.QtWidgets import QFileDialog
        w = self.win
        mp3 = make_file("purr.mp3")
        orig = QFileDialog.getOpenFileName
        try:
            QFileDialog.getOpenFileName = staticmethod(lambda *a, **kw: (mp3, ""))
            w._pick_sound("record_start")
            QFileDialog.getOpenFileName = staticmethod(lambda *a, **kw: (make_file("x.txt", b"hi"), ""))
            w._pick_sound("countdown")
        finally:
            QFileDialog.getOpenFileName = orig
        if sounds.media_supported():
            self.assertEqual(w.settings.sound_custom, {"record_start": mp3})
            self.assertEqual(self.media.played[-1][0], "purr.mp3")          # preview
        self.assertIn("x.txt", w.status_lore.text().replace("\xa0", " "))
        self.media.errors[mp3] = "Could not open file"
        w._preview_sound("record_start")
        self.assertIn("purr.mp3", w.status_lore.text().replace("\xa0", " "))
        self.assertEqual(self.wav.played[-1][0], "meow.wav")                 # the default instead
        lbl, _ = w.sound_files["record_start"]
        self.assertIn(i18n.tr("snd_broken", name="").strip(), lbl.text())


if __name__ == "__main__":
    unittest.main()
