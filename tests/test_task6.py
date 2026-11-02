"""Round six: KotoClick rename (settings folder migration, old env names), the new bot link,
the build script and English-only developer comments."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["KOTOCLICK_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["KOTOCLICK_SOUND"] = "off"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import app  # noqa: E402
from app import i18n, paths, promo  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.typography import nbsp  # noqa: E402

NEW_URL = "https://t.me/DownGrabBot?start=KotoClick"


class NoOverrides:
    """Context: no KOTOCLICK_/KOTOKLIK_ dir overrides, the system settings root is a temp folder."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp())

    def __enter__(self):
        env = {k: v for k, v in os.environ.items()
               if not (k.startswith("KOTOCLICK_") or k.startswith("KOTOKLIK_")) or k.endswith("SOUND")}
        self._env = mock.patch.dict(os.environ, env, clear=True)
        self._env.start()
        self._root = mock.patch.object(paths, "config_root", lambda: self.root)
        self._root.start()
        return self.root

    def __exit__(self, *exc):
        self._root.stop()
        self._env.stop()


class NameTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(app.APP_NAME, "KotoClick")
        self.assertEqual(app.LEGACY_APP_NAME, "Kotoklik")

    def test_titles(self):
        self.assertEqual(i18n.STRINGS["en"]["app_title"], "KotoClick")
        self.assertTrue(i18n.STRINGS["en"]["window_title"].startswith("KotoClick"))
        self.assertEqual(i18n.STRINGS["ru"]["app_title"], "Котоклик")
        self.assertTrue(i18n.STRINGS["ru"]["window_title"].startswith("Котоклик"))
        for text in i18n.STRINGS["en"].values():
            self.assertNotIn("Kotoklik", text)


class EnvTests(unittest.TestCase):
    def test_new_and_old_env_names(self):
        with mock.patch.dict(os.environ, {"KOTOKLIK_MACROS_DIR": "/old"}, clear=False):
            os.environ.pop("KOTOCLICK_MACROS_DIR", None)
            self.assertEqual(paths.env("MACROS_DIR"), "/old")
            os.environ["KOTOCLICK_MACROS_DIR"] = "/new"
            self.assertEqual(paths.env("MACROS_DIR"), "/new")


class MigrationTests(unittest.TestCase):
    def make_old(self, root: Path):
        old = root / "Kotoklik"
        (old / "macros").mkdir(parents=True)
        (old / "sounds_custom").mkdir()
        (old / "settings.json").write_text(json.dumps({"language": "en", "repeat_count": 250}), encoding="utf-8")
        (old / "macros" / "Farm.json").write_text("{}", encoding="utf-8")
        (old / "sounds_custom" / "meow.wav").write_bytes(b"RIFF")
        return old

    def test_old_folder_is_copied_not_moved(self):
        with NoOverrides() as root:
            old = self.make_old(root)
            new = paths.config_dir()
            self.assertEqual(new, root / "KotoClick")
            self.assertTrue((new / "settings.json").is_file())
            self.assertTrue((new / "macros" / "Farm.json").is_file())
            self.assertTrue((new / "sounds_custom" / "meow.wav").is_file())
            self.assertEqual(paths.macros_dir(), new / "macros")
            # the old folder is never deleted
            self.assertTrue((old / "settings.json").is_file())
            self.assertTrue((old / "macros" / "Farm.json").is_file())
            s = Settings.load()
            self.assertEqual((s.language, s.repeat_count), ("en", 250))
            # copied only once: later changes to the old folder are not copied again
            (old / "macros" / "Later.json").write_text("{}", encoding="utf-8")
            paths.config_dir()
            self.assertFalse((new / "macros" / "Later.json").exists())

    def test_copy_failure_keeps_using_old_folder(self):
        with NoOverrides() as root:
            old = self.make_old(root)
            with mock.patch.object(paths.shutil, "copytree", side_effect=OSError("disk full")):
                self.assertEqual(paths.config_dir(), old)
                self.assertEqual(Settings.load().language, "en")
            self.assertTrue((old / "settings.json").is_file())

    def test_old_settings_read_when_new_folder_has_none(self):
        with NoOverrides() as root:
            old = self.make_old(root)
            (root / "KotoClick").mkdir()          # new folder exists already, but empty
            self.assertEqual(paths.config_dir(), root / "KotoClick")
            s = Settings.load()
            self.assertEqual(s.language, "en")    # read from the old settings.json
            s.repeat_count = 400
            s.save()
            self.assertTrue((root / "KotoClick" / "settings.json").is_file())
            self.assertEqual(json.loads((old / "settings.json").read_text(encoding="utf-8"))["repeat_count"], 250)
            self.assertEqual(Settings.load().repeat_count, 400)

    def test_fresh_install(self):
        with NoOverrides() as root:
            self.assertEqual(paths.config_dir(), root / "KotoClick")
            self.assertFalse((root / "Kotoklik").exists())
            self.assertEqual(Settings.load().repeat_count, Settings().repeat_count)

    def test_new_folder_wins(self):
        with NoOverrides() as root:
            self.make_old(root)
            new = root / "KotoClick"
            new.mkdir()
            (new / "settings.json").write_text(json.dumps({"language": "ru"}), encoding="utf-8")
            self.assertEqual(Settings.load().language, "ru")


class LinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main as app_main
        cls.app = app_main.create_app([])

    def test_url(self):
        self.assertEqual(promo.PROMO_URL, NEW_URL)

    def test_nbsp_keeps_query_string(self):
        for lang in ("ru", "en"):
            text = nbsp(i18n.STRINGS[lang]["promo"].format(url=promo.PROMO_URL))
            self.assertIn(f'<a href="{NEW_URL}">', text)

    def test_link_opens_only_on_click_with_full_url(self):
        from PySide6.QtCore import QUrl
        from app.ui.cat import PromoToast
        opened = []
        with mock.patch("app.ui.cat.QDesktopServices.openUrl", side_effect=lambda u: opened.append(u)):
            t = PromoToast(promo.PROMO_URL)
            t.set_text(nbsp(i18n.STRINGS["en"]["promo"].format(url=promo.PROMO_URL)))
            t.popup()
            self.assertEqual(opened, [])
            t.label.linkActivated.emit(NEW_URL)
            self.assertEqual(len(opened), 1)
            self.assertIsInstance(opened[0], QUrl)
            self.assertEqual(opened[0].toString(), NEW_URL)
            self.assertEqual(opened[0].query(), "start=KotoClick")
            t.deleteLater()


class ProjectFilesTests(unittest.TestCase):
    def test_build_bat(self):
        raw = (ROOT / "build.bat").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))       # CRLF only
        text = raw.decode("utf-8")
        self.assertIn("--name KotoClick ", text)
        self.assertIn(r'--icon "%ROOT%\assets\kotoclick.ico"', text)
        self.assertIn('del /q "Kotoklik.spec"', text)
        self.assertIn('del /q "KotoClick.spec"', text)
        self.assertIn('del /q "Kotoklik.exe"', text)
        self.assertIn(r'explorer /select,"%ROOT%\KotoClick.exe"', text)
        self.assertTrue((ROOT / "assets" / "kotoclick.ico").is_file())

    def test_no_cyrillic_in_developer_comments(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import check_comments
        self.assertEqual(check_comments.scan(ROOT), {})


if __name__ == "__main__":
    unittest.main()
