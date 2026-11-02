"""Checks that no text in the KotoClick window is clipped.
Goes through all three tabs, both languages and all cat states, and the step dialog
for every step type.
   python tools/check_layout.py            (100 % scale)
   QT_SCALE_FACTOR=1.5 python tools/check_layout.py   (like Windows at 150 % scaling)
Exits with code 1 and a list of problems if something does not fit."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KOTOCLICK_CONFIG_DIR", tempfile.mkdtemp())
os.environ.setdefault("KOTOCLICK_SOUND", "off")
_cfg = os.path.join(tempfile.mkdtemp(), "screen.json")
with open(_cfg, "w") as fh:
    fh.write('{"screens": [{"name": "s", "x": 0, "y": 0, "width": 1920, "height": 1080, '
             '"logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}')
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen:configfile=" + _cfg)

from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QLabel,  # noqa: E402
                               QLineEdit)

import main as app_main  # noqa: E402
from app.hotkeys import pretty_key  # noqa: E402
from app.i18n import tr  # noqa: E402
from app.macro import Step  # noqa: E402

SLACK = 1


def problems_in(win, where):
    out = []
    for w in win.findChildren(QLabel) + win.findChildren(QAbstractButton):
        if not w.isVisibleTo(win) or not w.text():
            continue
        name = f"{where} {type(w).__name__} {w.text()[:40]!r}"
        if isinstance(w, QLabel) and w.wordWrap():
            need = w.heightForWidth(w.width())
            if need > w.height() + SLACK:
                out.append(f"{name}: needs height {need} > {w.height()}")
        else:
            hint = w.sizeHint()
            if hint.width() > w.width() + SLACK:
                out.append(f"{name}: needs width {hint.width()} > {w.width()}")
            if hint.height() > w.height() + SLACK:
                out.append(f"{name}: needs height {hint.height()} > {w.height()}")
    for w in win.findChildren(QAbstractSpinBox):
        if w.isVisibleTo(win):
            le = w.findChild(QLineEdit)
            need = QFontMetrics(w.font()).horizontalAdvance(w.text()) + 8
            if need > le.width() + SLACK:
                out.append(f"{where} spinbox {w.text()!r}: needs {need} > {le.width()}")
    t = getattr(win, "table", None)
    if t is not None and t.isVisibleTo(win):
        hh = t.horizontalHeader()
        fm = QFontMetrics(hh.font())
        for c in range(t.columnCount()):
            text = t.horizontalHeaderItem(c).text()
            need = fm.horizontalAdvance(text) + 16
            if need > hh.sectionSize(c) + SLACK:
                out.append(f"{where} header {text!r}: needs {need} > {hh.sectionSize(c)}")
            for r in range(t.rowCount()):
                it = t.item(r, c)
                need = QFontMetrics(t.font()).horizontalAdvance(it.text()) + 20
                if need > t.columnWidth(c) + SLACK:
                    out.append(f"{where} cell {it.text()!r}: needs {need} > {t.columnWidth(c)}")
    return out


def phrase_samples(lang):
    """All cat phrases with the longest placeholders (big numbers, a long key name)."""
    from app import i18n
    from app.phrases import PHRASES, fields
    i18n.set_language(lang)
    big = "1 000 000" if lang == "ru" else "1,000,000"
    longest_key = max((pretty_key(k) for k in ("caps_lock", "shift_r", "ctrl_r", "alt_r", "page_down",
                                               "print_screen", "scroll_lock", "num_lock")), key=len)
    for situation, bank in PHRASES.items():
        for p in bank[lang]:
            words = [""]
            if "w" in fields(p):
                words = list(i18n.PLURALS[lang].values())
                words = [w for forms in words for w in forms]
            for w in words:
                yield situation, p.format(n=big, w=w, key=longest_key)


def check_phrases(win, app):
    """Every cat phrase must fit into the bubble completely."""
    out = []
    win.settings.chatty = True
    for lang in ("ru", "en"):
        win.set_language(lang)
        win._set_tab(0, save=False)
        win.set_state("idle")
        win._flash_text = ""
        for situation, text in phrase_samples(lang):
            win._phrase, win._phrase_state = text, win.state
            win._refresh_texts()
            app.processEvents()
            lore = win.status_lore
            need = lore.heightForWidth(lore.width())
            if lore.text().replace("\xa0", " ") != text:
                out.append(f"[{lang} phrase {situation}] not shown: {text!r}")
            elif need > lore.height() + SLACK:
                out.append(f"[{lang} phrase {situation}] {text!r}: needs height {need} > {lore.height()}")
    win._phrase = ""
    return out


def check_step_dialogs(win, app):
    """The "add / edit step" dialog: every step type, both languages, nothing clipped."""
    from app.ui.step_dialog import StepDialog
    out = []
    samples = [Step("click", 1920, 1080, "middle", 99999, double=True), Step("move", 900, 470),
               Step("wait", delay_ms=3_600_000), Step("mouse_down", 1920, 1080, "middle", 99999),
               Step("mouse_up", 1920, 1080, "right", 99999), Step("scroll", 1920, 1080, delay_ms=99999, dx=-100, dy=-100)]
    for lang in ("ru", "en"):
        win.set_language(lang)
        for step in samples:
            d = StepDialog(step, lambda: (0, 0), win)
            d.show()
            app.processEvents()
            if d.layout().minimumSize().width() > d.width() or d.layout().minimumSize().height() > d.height():
                out.append(f"[{lang} dialog {step.kind}] layout does not fit: {d.size()}")
            out += problems_in(d, f"[{lang} dialog {step.kind}]")
            d.close()
            d.deleteLater()
    return out


def run():
    app = app_main.create_app([])
    win, _ = app_main.build_window(app)
    win.macro.steps = [Step("click", 1920, 1080, "middle", 99999, double=True), Step("wait", delay_ms=500),
                       Step("move", 900, 470), Step("key", action="release", key="shift_r"),
                       Step("key", action="press", key="caps_lock"), Step("key", action="press", char="ж", vk=186),
                       Step("mouse_down", 1920, 1080, "middle", 99999), Step("mouse_up", 1920, 1080, "middle", 99999),
                       Step("scroll", 1920, 1080, delay_ms=99999, dx=-100, dy=-100), Step("scroll", 1, 1, dy=7)]
    win._fill_table()
    win.show()
    app.processEvents()
    problems = []
    from app.ui.main_window import WIN_W, WIN_H
    if (win.width(), win.height()) != (WIN_W, WIN_H) or win.minimumSize() != win.maximumSize():
        problems.append(f"window is not fixed: {win.size()}")
    if win.centralWidget().layout().minimumSize().height() > WIN_H:
        problems.append("layout needs more height than the window has")
    for keys in (("f6", "f7", "f8", "f9"), ("ctrl_r", "shift_r", "alt_r", "caps_lock")):
        for btn, k in zip((win.key_click, win.key_record, win.key_play, win.key_panic), keys):
            btn.set_key(k, pretty_key(k))
        win.settings.hotkey_click, win.settings.hotkey_record, win.settings.hotkey_play, win.settings.hotkey_panic = keys
        for lang in ("ru", "en"):
            win.set_language(lang)
            for btn, k in zip((win.key_click, win.key_record, win.key_play, win.key_panic), keys):
                btn.set_key(k, pretty_key(k))
            for tab in (0, 1, 2):
                win._set_tab(tab, save=False)
                for unit in ("ms", "s"):
                    win.interval_unit.set_value(unit)
                    win._on_unit_changed(unit)
                    for state in ("idle", "countdown", "clicking", "recording", "playing"):
                        win._countdown_left = 3
                        win.set_state(state)
                        app.processEvents()
                        problems += problems_in(win, f"[{lang} tab{tab} {unit} {state} {keys[0]}]")
                    # countdown before recording and the cat's reactions
                    win._countdown_action = win._begin_recording
                    win.set_state("countdown")
                    app.processEvents()
                    problems += problems_in(win, f"[{lang} tab{tab} {unit} countdown-rec {keys[0]}]")
                    win._countdown_action = None
                    win.set_state("clicking")
                    for mood in ("lively", "hyper", "disco"):
                        win.cat.mood.state = mood
                        win._refresh_texts()
                        app.processEvents()
                        problems += problems_in(win, f"[{lang} tab{tab} {unit} mood {mood} {keys[0]}]")
                    win.cat.mood.state = "calm"
                    win.set_state("idle")
                for key, kw in (("msg_recorded", {"n": 99999, "word": "шагов", "name": "Н" * 22}),
                                ("msg_created", {"name": "Ж" * 22}), ("msg_bad_wav", {"name": "Ж" * 22}),
                                ("msg_bad_format", {"name": "Ж" * 22}), ("msg_bad_sound", {"name": "Ж" * 22}),
                                ("msg_no_media", {}), ("msg_lib_fail", {"err": "X" * 300}), ("msg_no_audio", {})):
                    win.flash(tr(key, **kw))
                    app.processEvents()
                    problems += problems_in(win, f"[{lang} tab{tab} flash {key}]")
                for key in ("msg_key_busy", "msg_empty", "msg_key_step_edit", "msg_select_rows",
                            "msg_stop_first", "err_record", "err_play"):
                    win.flash(tr(key, key=pretty_key(keys[1]), err="X" * 300))
                    app.processEvents()
                    problems += problems_in(win, f"[{lang} tab{tab} flash {key}]")
        for lang in ("ru", "en"):
            win.set_language(lang)
            win.show_promo()
            app.processEvents()
            problems += problems_in(win, f"[{lang} promo]")
            t = win.promo_toast
            if t.geometry().bottom() > win.centralWidget().height() or t.y() < 0:
                problems.append(f"[{lang} promo] toast out of window: {t.geometry()}")
            t.hide()
    problems += check_phrases(win, app)
    problems += check_step_dialogs(win, app)
    win.set_state("idle")
    win.set_language("ru")
    win.close()
    return sorted(set(problems))


if __name__ == "__main__":
    found = run()
    for p in found:
        print(p)
    print(f"scale={os.environ.get('QT_SCALE_FACTOR', '1')} problems={len(found)}")
    sys.exit(1 if found else 0)
