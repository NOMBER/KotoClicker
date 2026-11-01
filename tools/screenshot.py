"""Screenshot of the main window without showing it on screen (for design checks).
   python tools/screenshot.py out.png [tab] [state] [ru|en]
   python tools/screenshot.py out.png [tab] [state] [ru|en] [situation[:n[:noun]]]
   state: idle | clicking | recording | playing | countdown | disco | promo
          | dialog:KIND  (the step editor for a step type, e.g. dialog:scroll or dialog:mouse_down)
   On tab 1 the open macro is the "Drag demo": a hold, a drag & drop and wheel turns.
   situation: a situation from phrases.py, e.g. hyper or record_done:12:step
   Windows scaling can be simulated like this: QT_SCALE_FACTOR=1.5 python tools/screenshot.py ..."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KOTOCLICK_CONFIG_DIR", tempfile.mkdtemp())
os.environ.setdefault("KOTOCLICK_SOUND", "off")
# a virtual 1920x1080 screen so the window is not clipped
_cfg = os.path.join(tempfile.mkdtemp(), "screen.json")
with open(_cfg, "w") as fh:
    fh.write('{"screens": [{"name": "s", "x": 0, "y": 0, "width": 1920, "height": 1080, '
             '"logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}')
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen:configfile=" + _cfg)

from PySide6.QtCore import QTimer  # noqa: E402

import main as app_main  # noqa: E402
from kotoclick.macro import Step  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
tab = int(sys.argv[2]) if len(sys.argv) > 2 else 0
state = sys.argv[3] if len(sys.argv) > 3 else "idle"
lang = sys.argv[4] if len(sys.argv) > 4 else "ru"
say = sys.argv[5] if len(sys.argv) > 5 else ""

app = app_main.create_app()
win, _ = app_main.build_window(app)
win.set_language(lang)
ru = lang == "ru"
for extra in (("Демо перетаскивания", "Сбор морковки", "Фарм в шахте", "Автоклик по печеньке") if ru else
              ("Drag demo", "Carrot harvest", "Mine farming", "Cookie clicker")):
    win.library.create(extra)
win._switch_macro("Демо перетаскивания" if ru else "Drag demo")
# "Drag demo": drag a file into a folder, scroll the list, click, hold the right button
win.macro.steps = [Step("mouse_down", 640, 380, "left", 400),
                   Step("move", 860, 430, delay_ms=50),
                   Step("mouse_up", 1040, 460, "left", 60),
                   Step("scroll", 900, 600, delay_ms=300, dy=-3),
                   Step("scroll", 900, 600, delay_ms=700, dy=2),
                   Step("wait", delay_ms=500),
                   Step("click", 640, 380, "left", 0),
                   Step("mouse_down", 1210, 96, "right", 400), Step("mouse_up", 1210, 96, "right", 800),
                   Step("key", action="press", key="ctrl_l", delay_ms=300),
                   Step("key", action="press", char="c", vk=67, delay_ms=80),
                   Step("key", action="release", char="c", vk=67, delay_ms=60),
                   Step("key", action="release", key="ctrl_l", delay_ms=40)]
win._fill_table()
win._set_tab(tab, save=False)
win.table.selectRow(1 if tab == 1 else 5)
dialog = None
win.engine.clicks, win.engine.total_clicks = (1337, 4096) if state not in ("idle", "promo") else (0, 0)
if state == "disco":
    # simulate "very fast and long": 20 clicks/s for 6 seconds already
    win.set_state("clicking")
    win.cat.mood.state, win.cat.mood.intensity = "disco", 1.0
    win.cat.mood.update = lambda *a, **k: "disco"     # keep the disco going until the screenshot

    def more_clicks():
        win.engine.total_clicks += 1
        win.engine.clicks += 1
    feeder = QTimer(win, interval=50)
    feeder.timeout.connect(more_clicks)
    feeder.start()
    win._refresh_texts()
elif state.startswith("dialog"):
    from kotoclick.ui.step_dialog import StepDialog
    kind = state.partition(":")[2] or "scroll"
    sample = {"scroll": Step("scroll", 900, 600, delay_ms=300, dy=-3),
              "mouse_down": Step("mouse_down", 640, 380, "left", 400),
              "mouse_up": Step("mouse_up", 1040, 460, "left", 60)}.get(kind, Step(kind, 640, 380))
    dialog = StepDialog(sample, lambda: (0, 0), win)
elif state not in ("idle", "promo"):
    win.set_state(state)
win.show()
if dialog is not None:
    dialog.show()
if say:
    # make the cat say a phrase of the given situation (after the greeting)
    sit, _, rest = say.partition(":")
    num, _, noun = rest.partition(":")
    QTimer.singleShot(50, lambda: win._say(sit, n=int(num) if num else None, noun=noun or None,
                                           key="F6"))
if state == "promo":
    QTimer.singleShot(100, win.show_promo)


def snap():
    (dialog or win).grab().save(out)
    print("saved", out)
    app.quit()


QTimer.singleShot(700, snap)
app.exec()
