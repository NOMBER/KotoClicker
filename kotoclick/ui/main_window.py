"""KotoClick main window.

App states:
  idle       - the cat is dozing
  countdown  - the cat is stretching (3 seconds for you to move the cursor off the button)
  clicking   - simple auto-click
  recording  - the mouse is recording a macro
  playing    - the cat is replaying a macro

While clicking, the cat reacts to the click rate (calm / lively / hyper / disco,
see reactions.py). Macros live in the library (library.py), sounds in sounds.py,
the Telegram bot bubble in promo.py + PromoToast.

The window has a fixed size (it does not stretch): the whole layout is designed
for WIN_W x WIN_H, and every text fits in both Russian and English.
The size is chosen so the window fits even a 1920x1080 screen at 150 % scaling.
"""
import random
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDoubleSpinBox,
                               QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QSlider, QSpinBox, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget, QFrame,
                               QGraphicsOpacityEffect)

from .. import i18n, paths
from ..hotkeys import pretty_key
from ..i18n import plural, tr
from ..library import MacroLibrary
from ..macro import Macro, Step
from ..promo import PROMO_URL, EasterEgg, PromoScheduler
from ..phrases import PhrasePicker, greeting_situation, milestone_reached
from ..settings import HOTKEY_DEFAULTS
from ..sound_trim import TrimError, load_pcm, save_trimmed
from ..sounds import (EVENTS, SoundBoard, check_sound, default_path, max_seconds_for, media_supported,
                      needs_media)
from ..typography import nbsp, tooltip_html
from . import theme
from .cat import CatView, DiscoPanel, PromoToast
from .step_dialog import StepDialog
from .trim_dialog import TrimDialog
from .widgets import (Card, CardIcon, ChevronCombo, KeyCaptureButton, MascotView, PawBackground,
                      PawButton, Segmented, Switch, add_shadow, card_header, set_ui_animations)

WIN_W, WIN_H = 1180, 624
STATUS = {  # translation keys: (title, explanation)
    "idle": ("st_idle", "st_idle_lore"),
    "countdown": ("st_countdown", "st_countdown_lore"),
    "clicking": ("st_clicking", "st_clicking_lore"),
    "recording": ("st_recording", "st_recording_lore"),
    "playing": ("st_playing", "st_playing_lore"),
}
MOOD_STATUS = {  # the cat's reactions to the click rate
    "lively": ("st_lively", "st_lively_lore"),
    "hyper": ("st_hyper", "st_hyper_lore"),
    "disco": ("st_disco", "st_disco_lore"),
}
COL_N, COL_ACT, COL_X, COL_Y, COL_DELAY = range(5)
AUTOSAVE_NAME = "autosave_macro.json"   # old autosave (pre-library): migrated into the library
COUNTDOWN_SECONDS = 3
# "Chatty cat": how often the phrase changes by itself (seconds, random within the range)
CHAT_EVERY = {"idle": (40, 90), "recording": (20, 35), "clicking": (45, 80)}
LOOP_PHRASE_GAP = 12.0    # talk about macro loops at most once every 12 s


def _short(name: str, limit: int = 22) -> str:
    """Long names in messages are shortened so the status line does not overflow."""
    return name if len(name) <= limit else name[:limit - 1] + "…"
FLASH_MAX = 100   # long messages are shortened to fit the bubble (full text in the tooltip)
EDIT_TRIGGERS = (QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                 | QAbstractItemView.SelectedClicked)


def _card(margins=(18, 12, 18, 12), spacing=10, shadow=True, horizontal=False):
    c = Card(shadow=shadow)
    lay = (QHBoxLayout if horizontal else QVBoxLayout)(c)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return c, lay


def _label(object_name="", wrap=False):
    lbl = QLabel()
    if object_name:
        lbl.setObjectName(object_name)
    lbl.setWordWrap(wrap)
    return lbl


class MainWindow(QMainWindow):
    def __init__(self, settings, engine, hotkeys, parent=None, sound_backend=None, library_dir=None,
                 sound_media=None):
        super().__init__(parent)
        self.settings = settings
        self.engine = engine
        self.hotkeys = hotkeys
        self.state = "idle"
        self.macro = Macro()
        self._capture_target = None
        self._countdown_left = 0
        self._countdown_action = None
        self._last_counter = (-1, -1)
        self._filling_table = False
        self._flash_text = ""
        self._tr_hooks = []          # functions that set the texts again when the language changes
        self._loading_macro = False
        if not settings.language:
            # first run: language as in Windows (Russian / Ukrainian / Belarusian -> RU, otherwise EN);
            # saved to the settings right away; a manual choice always wins afterwards
            settings.language = i18n.detect_language()
            self._first_lang = True
        else:
            self._first_lang = False
        i18n.set_language(settings.language)
        self.sounds = SoundBoard(settings, sound_backend, media=sound_media, on_error=self._on_sound_error)
        # the cat's phrases (phrases.py): one current phrase for the current state
        self.phrases = PhrasePicker()
        self._phrase = ""
        self._phrase_state = None
        self._phrase_ctx = None        # what was said, so it can be repeated in the other language
        self._milestone = 0
        self._last_loop = 0
        self._last_loop_said = 0.0
        self._stop_reason = None       # "user" = stopped with a key/the paw, None = finished by itself
        self._said_mood = "calm"
        self._fade_anim = None
        self.library = MacroLibrary(library_dir or paths.library_dir())
        self.current_macro = ""
        self.promo = PromoScheduler(time.monotonic())
        self.egg = EasterEgg()        # 10 quick clicks on the cat
        self._key_hooks = []           # texts that mention hotkeys

        self.setWindowIcon(QIcon(paths.asset("kotoclick.ico")))
        # A normal window, but without the "maximize" button and without resizing
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
                            | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint
                            | Qt.WindowCloseButtonHint)
        self.setFixedSize(WIN_W, WIN_H)

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self._save_settings)
        self._counter_timer = QTimer(self, interval=100)
        self._counter_timer.timeout.connect(self._update_counter)
        self._counter_timer.start()
        self._countdown_timer = QTimer(self, interval=1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._flash_timer = QTimer(self, singleShot=True, interval=3500)
        self._flash_timer.timeout.connect(self._clear_flash)
        self._tick_timer = QTimer(self, interval=1000)          # quiet ticks while recording
        self._tick_timer.timeout.connect(lambda: self.sounds.play("tick"))
        self._macro_save_timer = QTimer(self, singleShot=True, interval=700)
        self._macro_save_timer.timeout.connect(self._autosave_macro)
        self._promo_timer = QTimer(self, interval=10_000)       # every 10 s: is it time to show off the bot?
        self._promo_timer.timeout.connect(self._check_promo)
        self._promo_timer.start()
        self._chat_timer = QTimer(self, singleShot=True)        # the cat sometimes says something new
        self._chat_timer.timeout.connect(self._chat_tick)

        self._build_ui()
        self._load_settings_into_ui()
        self._init_library()
        self._connect_engine()
        self._update_watched()
        self.set_state("idle")
        self._say(greeting_situation(datetime.now().hour))
        if self._first_lang:
            self._save_timer.start()

    # ================================================================ translations
    def _tr(self, fn):
        """Remember how to set a text, and set it right away."""
        self._tr_hooks.append(fn)
        fn()

    def _text(self, widget, key, method="setText"):
        if method == "setToolTip":
            self._tr(lambda: widget.setToolTip(tooltip_html(tr(key))))
        elif method == "setText" and isinstance(widget, QLabel) and widget.wordWrap():
            # wrapping labels: short words never stay at the end of a line
            self._tr(lambda: widget.setText(nbsp(tr(key))))
        else:
            self._tr(lambda: getattr(widget, method)(tr(key)))
        return widget

    def _keys_text(self, fn):
        """A text containing key names: set now, on language change and on key change."""
        self._key_hooks.append(fn)
        self._tr(fn)

    def _key_kw(self):
        """Placeholders with the real (configured) keys for all texts."""
        s = self.settings
        stop = pretty_key(s.hotkey_stop) if s.hotkey_stop else ""
        return dict(
            click=pretty_key(s.hotkey_click), record=pretty_key(s.hotkey_record),
            play=pretty_key(s.hotkey_play), panic=pretty_key(s.hotkey_panic), stop=stop,
            or_stop=tr("or_stop", key=stop) if stop else "",
            or_stop_paren=tr("or_stop_paren", key=stop) if stop else "",
            stop_part=tr("stop_part", key=stop) if stop else "",
            stop_any=stop or pretty_key(s.hotkey_panic),
            keys=", ".join(pretty_key(k) for k in self._app_keys_ordered()),
            n=self._countdown_left)

    def set_language(self, lang):
        """Switches the language on the fly, without a restart."""
        lang = i18n.set_language(lang)
        self.lang_seg.set_value(lang)
        changed = lang != self.settings.language
        if changed:
            self._set("language", lang)
        self._flash_text = ""
        self.retranslate()
        if changed:
            self._say("lang_switched")

    def retranslate(self):
        for fn in self._tr_hooks:
            fn()
        for btn, field in self._hotkey_fields().items():
            name = getattr(self.settings, field)
            btn.retranslate(pretty_key(name) if name else tr("hk_none"))
        self._apply_interval_unit(self.settings.interval_unit, self.interval.value())
        self.table.setHorizontalHeaderLabels([tr("col_n"), tr("col_action"), "X", "Y", tr("col_delay")])
        self._fill_table()
        self._last_counter = (-1, -1)
        self._update_counter()
        self._refresh_sound_files()
        self.set_state(self.state)

    # ================================================================ UI
    def _build_ui(self):
        root = PawBackground()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)
        outer.addWidget(self._build_left_panel())
        outer.addLayout(self._build_right_side(), 1)
        self.promo_toast = PromoToast(PROMO_URL, root)
        self._tr(lambda: self.promo_toast.set_text(nbsp(tr("promo", url=PROMO_URL))))
        self._tr(self._retitle)

    def _retitle(self):
        # Qt appends the app name to the title if it is missing there: keep both in the same language
        QApplication.setApplicationDisplayName(tr("app_title"))
        self.setWindowTitle(tr("window_title"))

    def _build_left_panel(self):
        panel = DiscoPanel()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(300)
        add_shadow(panel, blur=36, dy=8, alpha=130)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 14, 20, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(CardIcon("paw"))
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(self._text(_label("appTitle"), "app_title"))
        tcol.addWidget(self._text(_label("appSubtitle"), "app_subtitle"))
        head.addLayout(tcol, 1)
        lay.addLayout(head)

        self.cat = CatView(176, click_source=lambda: self.engine.total_clicks)
        self.cat.disco_panel = panel
        self.cat.moodChanged.connect(self._on_mood)
        self.cat.clicked.connect(self._on_cat_clicked)
        lay.addWidget(self.cat, 0, Qt.AlignHCenter)
        self.left_panel = panel

        bubble = self.bubble = QFrame()
        bubble.setObjectName("bubble")
        bubble.setFixedHeight(114)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(4)
        self.status_title = _label("statusTitle", wrap=True)
        self.status_title.setAlignment(Qt.AlignCenter)
        self.status_lore = _label("statusLore", wrap=True)
        self.status_lore.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        bl.addStretch(1)
        bl.addWidget(self.status_title)
        bl.addWidget(self.status_lore)
        bl.addStretch(1)
        lay.addWidget(bubble)

        self.counter = _label("counter")
        self.counter.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.counter)

        lay.addStretch(1)
        self.paw = PawButton(size=148)
        self.paw.clicked.connect(self._on_paw_clicked)
        lay.addWidget(self.paw, 0, Qt.AlignHCenter)
        self.hint = _label("hint", wrap=True)   # long key names wrap to a second line
        self.hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.hint)
        return panel

    def _build_right_side(self):
        col = QVBoxLayout()
        col.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(6, 6, 10, 6)
        bl.setSpacing(6)
        self.tab_buttons = []
        for i, key in enumerate(("tab_simple", "tab_macro", "tab_settings")):
            b = QPushButton()
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._set_tab(idx))
            self._text(b, key)
            bl.addWidget(b)
            self.tab_buttons.append(b)
        bl.addStretch(1)
        badge = _label("hint")
        self._text(badge, "badge")
        self._text(badge, "badge_tip", "setToolTip")     # multi-line tooltip (rich text)
        bl.addWidget(badge)
        bl.addSpacing(10)
        self.lang_seg = Segmented([("ru", "RU"), ("en", "EN")], object_name="lang", spacing=4)
        self.lang_seg.changed.connect(self.set_language)
        self._text(self.lang_seg, "lang_tip", "setToolTip")
        bl.addWidget(self.lang_seg)
        col.addWidget(bar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_simple_page())
        self.stack.addWidget(self._build_macro_page())
        self.stack.addWidget(self._build_settings_page())
        col.addWidget(self.stack, 1)
        col.addWidget(self._build_footer())
        return col

    def _header(self, layout, icon, title_key, hint_key=None, hint_fn=None):
        row, t, h = card_header(icon)
        self._text(t, title_key)
        if hint_fn is not None:
            self._tr(hint_fn)
        elif hint_key:
            self._text(h, hint_key)
        layout.addLayout(row)
        return h

    # ---------------------------------------------------------- simple mode
    def _build_simple_page(self):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        # Hotkey
        c, l = _card()
        self._header(l, "key", "hotkey_title", "hotkey_hint")
        r = QHBoxLayout()
        r.setSpacing(12)
        self.key_click = KeyCaptureButton()
        self.key_click.captureRequested.connect(self._begin_capture)
        r.addWidget(self.key_click)
        r.addWidget(self._text(_label("cardHint"), "hotkey_change"), 1)
        l.addLayout(r)
        grid.addWidget(c, 0, 0)

        # Interval (the hint shows how many clicks per second that is)
        c, l = _card()
        self.interval_hint = self._header(l, "clock", "interval_title", hint_fn=lambda: None)
        r = QHBoxLayout()
        r.setSpacing(10)
        self.interval = QDoubleSpinBox()
        self.interval.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.interval.setFixedWidth(130)
        self.interval.valueChanged.connect(self._on_interval_changed)
        self.interval_unit = Segmented([("ms", ""), ("s", "")])
        self._tr(lambda: self.interval_unit.set_texts({"ms": tr("unit_ms"), "s": tr("unit_s")}))
        self.interval_unit.changed.connect(self._on_unit_changed)
        r.addWidget(self.interval)
        r.addWidget(self.interval_unit)
        r.addStretch(1)
        l.addLayout(r)
        grid.addWidget(c, 0, 1)

        # Mouse button
        c, l = _card()
        self._header(l, "mouse", "button_title", "button_hint")
        self.button_seg = Segmented([("left", ""), ("right", ""), ("middle", "")])
        self._tr(lambda: self.button_seg.set_texts(
            {"left": tr("btn_left"), "right": tr("btn_right"), "middle": tr("btn_middle")}))
        self.button_seg.changed.connect(lambda v: self._set("button", v))
        l.addWidget(self.button_seg)
        grid.addWidget(c, 1, 0)

        # Click type
        c, l = _card()
        self._header(l, "double", "type_title", "type_hint")
        self.click_type = Segmented([("single", ""), ("double", "")])
        self._tr(lambda: self.click_type.set_texts({"single": tr("type_single"), "double": tr("type_double")}))
        self.click_type.changed.connect(lambda v: self._set("double_click", v == "double"))
        l.addWidget(self.click_type)
        grid.addWidget(c, 1, 1)

        # Repeat
        c, l = _card()
        self._header(l, "repeat", "repeat_title", "repeat_hint")
        r = QHBoxLayout()
        r.setSpacing(10)
        self.repeat_seg = Segmented([("forever", ""), ("count", "")])
        self._tr(lambda: self.repeat_seg.set_texts({"forever": tr("repeat_forever"), "count": tr("repeat_count")}))
        self.repeat_seg.changed.connect(self._on_repeat_mode)
        self.repeat_count = QSpinBox(minimum=1, maximum=10_000_000)
        self.repeat_count.setButtonSymbols(QSpinBox.NoButtons)
        self.repeat_count.setFixedWidth(130)
        self.repeat_count.valueChanged.connect(lambda v: self._set("repeat_count", v))
        r.addWidget(self.repeat_seg)
        r.addSpacing(6)
        r.addWidget(self.repeat_count)
        r.addWidget(self._text(_label("cardHint"), "times"))
        r.addStretch(1)
        l.addLayout(r)
        grid.addWidget(c, 2, 0, 1, 2)

        # The cat's tip
        c, l = _card(spacing=12, horizontal=True)
        l.addWidget(CardIcon("paw"), 0, Qt.AlignTop)
        tip = _label("cardHint", wrap=True)
        tip.setTextFormat(Qt.RichText)
        self._keys_text(lambda: tip.setText(nbsp(tr("tip", **self._key_kw()))))
        l.addWidget(tip, 1)
        grid.addWidget(c, 3, 0, 1, 2)

        grid.setRowStretch(4, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.simple_page = page
        return page

    # ---------------------------------------------------------- macros
    def _build_macro_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Header with the mouse
        head, hl = _card(margins=(18, 8, 10, 4), spacing=14, horizontal=True)
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        tcol.addWidget(self._text(_label("sectionTitle"), "macro_title"))
        tcol.addWidget(self._text(_label("mouseSays", wrap=True), "mouse_says"))
        keys = QHBoxLayout()
        keys.setSpacing(8)
        self.key_record = KeyCaptureButton()
        self.key_record.captureRequested.connect(self._begin_capture)
        self.key_play = KeyCaptureButton()
        self.key_play.captureRequested.connect(self._begin_capture)
        keys.addWidget(self._text(_label("cardHint"), "rec_label"))
        keys.addWidget(self.key_record)
        keys.addSpacing(12)
        keys.addWidget(self._text(_label("cardHint"), "play_label"))
        keys.addWidget(self.key_play)
        keys.addStretch(1)
        tcol.addSpacing(2)
        tcol.addLayout(keys)
        tcol.addSpacing(4)
        hl.addLayout(tcol, 1)

        sw = QVBoxLayout()
        sw.setSpacing(8)
        self.record_moves = Switch()
        self._text(self.record_moves, "rec_moves")
        self._text(self.record_moves, "rec_moves_tip", "setToolTip")
        self.record_moves.toggled.connect(lambda v: self._set("record_moves", v))
        self.record_keys = Switch()
        self._text(self.record_keys, "rec_keys")
        self._keys_text(lambda: self.record_keys.setToolTip(tooltip_html(tr("rec_keys_tip", **self._key_kw()))))
        self.record_keys.toggled.connect(lambda v: self._set("record_keys", v))
        sw.addStretch(1)
        sw.addWidget(self.record_moves)
        sw.addWidget(self.record_keys)
        sw.addStretch(1)
        hl.addLayout(sw)
        self.mouse_mascot = MascotView(paths.asset("mouse.png"), 100, glow=False, sleepy=False)
        hl.addWidget(self.mouse_mascot, 0, Qt.AlignBottom)
        lay.addWidget(head)

        # Toolbar
        # Library: macro list + "New" + the "More" menu
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.macro_combo = ChevronCombo()
        self.macro_combo.setCursor(Qt.PointingHandCursor)
        self.macro_combo.setMaxVisibleItems(14)
        self._text(self.macro_combo, "lib_tip", "setToolTip")
        self.macro_combo.activated.connect(self._on_macro_chosen)
        self.btn_record = QPushButton()
        self.btn_record.setObjectName("danger")
        self.btn_record.clicked.connect(lambda: self.toggle_recording(from_ui=True))
        self.btn_new = self._text(QPushButton(), "new")
        self.btn_new.setObjectName("accent")
        self.btn_new.clicked.connect(self._new_macro)
        self.btn_more = self._text(QPushButton(), "more")
        self.more_menu = QMenu(self)
        self.act_rename = self.more_menu.addAction("", self._rename_macro)
        self.act_duplicate = self.more_menu.addAction("", self._duplicate_macro)
        self.act_delete = self.more_menu.addAction("", self._delete_macro)
        self.more_menu.addSeparator()
        self.act_import = self.more_menu.addAction("", self._import_macro)
        self.act_export = self.more_menu.addAction("", self._export_macro)
        self.more_menu.addSeparator()
        self.act_folder = self.more_menu.addAction("", self._open_library_folder)
        for act, key in ((self.act_rename, "m_rename"), (self.act_duplicate, "m_duplicate"),
                         (self.act_delete, "m_delete"), (self.act_import, "m_import"),
                         (self.act_export, "m_export"), (self.act_folder, "m_folder")):
            self._text(act, key)
        self.btn_more.setMenu(self.more_menu)
        tools.addWidget(self.macro_combo, 1)
        for b in (self.btn_new, self.btn_more, self.btn_record):
            b.setCursor(Qt.PointingHandCursor)
            tools.addWidget(b)
        lay.addLayout(tools)

        # Steps table
        tc, tl = _card(margins=(10, 10, 10, 10), spacing=8, shadow=False)
        self.table = QTableWidget(0, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(EDIT_TRIGGERS)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.StrongFocus)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_N, QHeaderView.Fixed)
        hh.setSectionResizeMode(COL_ACT, QHeaderView.Stretch)
        for c_ in (COL_X, COL_Y):
            hh.setSectionResizeMode(c_, QHeaderView.Fixed)
            self.table.setColumnWidth(c_, 84)
        hh.setSectionResizeMode(COL_DELAY, QHeaderView.Fixed)
        self.table.setColumnWidth(COL_N, 52)
        self.table.setColumnWidth(COL_DELAY, 170)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self._text(self.table, "table_tip", "setToolTip")
        tl.addWidget(self.table, 1)

        er = QHBoxLayout()
        er.setSpacing(8)
        self.btn_add_click = self._text(QPushButton(), "add_click")
        self.btn_add_click.clicked.connect(self._add_click_step)
        self.btn_add_wait = self._text(QPushButton(), "add_wait")
        self.btn_add_wait.clicked.connect(self._add_wait_step)
        self.btn_del = self._text(QPushButton(), "delete")
        self.btn_del.clicked.connect(self._delete_steps)
        self.btn_up = QPushButton("▲")
        self._text(self.btn_up, "up_tip", "setToolTip")
        self.btn_up.clicked.connect(lambda: self._move_step(-1))
        self.btn_down = QPushButton("▼")
        self._text(self.btn_down, "down_tip", "setToolTip")
        self.btn_down.clicked.connect(lambda: self._move_step(1))
        self.btn_clear = self._text(QPushButton(), "clear")
        self.btn_clear.clicked.connect(self._clear_steps)
        self.edit_buttons = [self.btn_add_click, self.btn_add_wait, self.btn_del, self.btn_up, self.btn_down, self.btn_clear]
        for b in self.edit_buttons:
            b.setCursor(Qt.PointingHandCursor)
            er.addWidget(b)
        er.addStretch(1)
        self.macro_stats = _label("cardHint")
        er.addWidget(self.macro_stats)
        tl.addLayout(er)
        lay.addWidget(tc, 1)

        # Macro repeat
        rc, rl = _card(margins=(14, 6, 14, 6), horizontal=True)
        rl.addWidget(CardIcon("repeat", size=32))
        rl.addWidget(self._text(_label("cardTitle"), "macro_repeat_title"))
        rl.addSpacing(8)
        self.macro_repeat_seg = Segmented([("loop", ""), ("count", "")])
        self._tr(lambda: self.macro_repeat_seg.set_texts({"loop": tr("loop"), "count": tr("repeat_count")}))
        self.macro_repeat_seg.changed.connect(self._on_macro_repeat_mode)
        self.macro_repeat = QSpinBox(minimum=1, maximum=1_000_000)
        self.macro_repeat.setButtonSymbols(QSpinBox.NoButtons)
        self.macro_repeat.setFixedWidth(110)
        self.macro_repeat.valueChanged.connect(lambda v: self._set("macro_repeat_count", v))
        rl.addWidget(self.macro_repeat_seg)
        rl.addWidget(self.macro_repeat)
        rl.addWidget(self._text(_label("cardHint"), "times"))
        rl.addStretch(1)
        lay.addWidget(rc)
        self.macro_page = page
        return page

    def _build_footer(self):
        f, l = _card(margins=(16, 8, 16, 8), horizontal=True)
        dot = CardIcon("record", size=32)
        l.addWidget(dot)
        l.addWidget(self._text(_label("cardTitle"), "panic_title"))
        self.key_panic = KeyCaptureButton()
        self.key_panic.setMinimumWidth(112)
        self.key_panic.captureRequested.connect(self._begin_capture)
        l.addWidget(self.key_panic)
        panic_hint = _label("cardHint")
        self._keys_text(lambda: panic_hint.setText(
            tr("panic_hint", key=self._key_kw()["stop"]) if self.settings.hotkey_stop else tr("panic_hint_alone")))
        l.addWidget(panic_hint)
        l.addStretch(1)
        self.on_top = Switch()
        self._text(self.on_top, "on_top")
        self.on_top.toggled.connect(self._on_top_toggled)
        l.addWidget(self.on_top)
        return f

    # ================================================================ settings
    def _load_settings_into_ui(self):
        s = self.settings
        self.lang_seg.set_value(i18n.language())
        self._sync_key_buttons()
        self.interval_unit.set_value(s.interval_unit)
        self._apply_interval_unit(s.interval_unit, s.interval_value)
        self.button_seg.set_value(s.button)
        self.click_type.set_value("double" if s.double_click else "single")
        self.repeat_seg.set_value("forever" if s.repeat_forever else "count")
        self.repeat_count.setValue(s.repeat_count)
        self.repeat_count.setEnabled(not s.repeat_forever)
        self.record_moves.setChecked(s.record_moves)
        self.anim_master.setChecked(s.anim_enabled)
        self.anim_hat.setChecked(s.anim_hat)
        self.anim_disco.setChecked(s.anim_disco)
        self.chatty.setChecked(s.chatty)
        self._apply_anim()
        self.volume.setValue(s.sound_volume)
        self.volume_label.setText(f"{s.sound_volume}%")
        for ev, sw in self.sound_switches.items():
            sw.setChecked(getattr(s, f"sound_{ev}"))
        self.cd_record.setChecked(s.countdown_record)
        self.cd_play.setChecked(s.countdown_play)
        self._refresh_sound_files()
        self.record_keys.setChecked(s.record_keys)
        self.macro_repeat_seg.set_value("loop" if s.macro_loop else "count")
        self.macro_repeat.setValue(s.macro_repeat_count)
        self.macro_repeat.setEnabled(not s.macro_loop)
        self.on_top.setChecked(s.always_on_top)
        if s.always_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.table.setHorizontalHeaderLabels([tr("col_n"), tr("col_action"), "X", "Y", tr("col_delay")])
        self._set_tab(s.current_tab, save=False)

    def _set(self, field, value):
        setattr(self.settings, field, value)
        self._save_timer.start()

    def _save_settings(self):
        try:
            self.settings.save()
        except OSError as exc:
            self.flash(tr("msg_settings_fail", err=exc))

    def _apply_interval_unit(self, unit, value):
        self.interval.blockSignals(True)
        if unit == "ms":
            self.interval.setDecimals(0)
            self.interval.setRange(1, 3_600_000)
            self.interval.setSingleStep(10)
            self.interval.setSuffix(tr("suffix_ms"))
        else:
            self.interval.setDecimals(2)
            self.interval.setRange(0.01, 3600)
            self.interval.setSingleStep(0.1)
            self.interval.setSuffix(tr("suffix_s"))
        self.interval.setValue(value)
        self.interval.blockSignals(False)
        self._update_rate_label()

    def _on_unit_changed(self, unit):
        if unit == self.settings.interval_unit:
            return
        seconds = self.settings.interval_seconds
        value = seconds * 1000 if unit == "ms" else seconds
        self.settings.interval_unit = unit
        self._apply_interval_unit(unit, value)
        self._set("interval_value", self.interval.value())

    def _on_interval_changed(self, v):
        self._set("interval_value", float(v))
        self._update_rate_label()

    def _update_rate_label(self):
        per_sec = 1.0 / self.settings.interval_seconds
        if per_sec >= 1:
            rate = tr("rate_per_sec", n=f"{per_sec:.0f}", word=plural(round(per_sec), "click"))
        else:
            n = f"{per_sec * 60:.1f}"
            rate = tr("rate_per_min", n=n.replace(".", ",") if i18n.language() == "ru" else n)
        self.interval_hint.setText(tr("interval_hint", rate=rate))

    def _on_repeat_mode(self, mode):
        self._set("repeat_forever", mode == "forever")
        self.repeat_count.setEnabled(mode != "forever")

    def _on_macro_repeat_mode(self, mode):
        self._set("macro_loop", mode == "loop")
        self.macro_repeat.setEnabled(mode != "loop")

    def _on_top_toggled(self, on):
        self._set("always_on_top", on)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def _set_tab(self, idx, save=True):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.tab_buttons):
            b.setChecked(i == idx)
        if save:
            self._set("current_tab", idx)
        self._refresh_texts()

    # ================================================================ hotkeys
    def _hotkey_fields(self):
        """Button -> settings field. Several buttons show the same key
        (on its own tab and in "Settings -> Hotkeys"); they are always in sync."""
        fields = {self.key_click: "hotkey_click", self.key_record: "hotkey_record",
                  self.key_play: "hotkey_play", self.key_panic: "hotkey_panic"}
        fields.update(getattr(self, "hk_buttons", {}))
        return fields

    def _app_keys_ordered(self):
        s = self.settings
        return [k for k in (getattr(s, f) for f in HOTKEY_DEFAULTS) if k]

    def _app_keys(self):
        """All keys that control KotoClick itself (they must not be recorded into a macro).
        Esc is included only if it is assigned as the stop key."""
        return set(self._app_keys_ordered())

    def _sync_key_buttons(self):
        for btn, field in self._hotkey_fields().items():
            name = getattr(self.settings, field)
            btn.set_key(name, pretty_key(name) if name else tr("hk_none"))
        if hasattr(self, "hk_clear"):
            self.hk_clear.setEnabled(bool(self.settings.hotkey_stop))

    def _keys_changed(self):
        """Keys changed: update the listener, the buttons and every text with key names."""
        self._sync_key_buttons()
        self._update_watched()
        for fn in self._key_hooks:
            fn()
        self._refresh_texts()

    def _update_watched(self):
        self.hotkeys.set_watched(self._app_keys())

    def _begin_capture(self, button):
        if self.state != "idle":
            self.flash(tr("msg_stop_first"))
            return
        prev = self._capture_target
        if prev is not None:
            prev.set_capturing(False)
            self._capture_target = None
            self.hotkeys.cancel_capture()
            if prev is button:          # a second click on the same button cancels
                return
        self._capture_target = button
        button.set_capturing(True)
        self.hotkeys.begin_capture()

    def on_key_captured(self, name):
        btn = self._capture_target
        if btn is None:
            return
        self._capture_target = None
        field = self._hotkey_fields()[btn]
        if name == "esc" and field != "hotkey_stop":
            btn.set_capturing(False)        # Esc means "cancel" (except in the second stop key slot)
            return
        for other, f in self._hotkey_fields().items():
            if f != field and getattr(self.settings, f) == name:
                btn.set_capturing(False)
                self.flash(tr("msg_key_busy", key=pretty_key(name)))
                return
        self._set(field, name)
        self._keys_changed()
        self.flash(tr("msg_key_set", key=pretty_key(name)))
        self._say("hotkey_set", key=pretty_key(name))

    def _clear_stop_key(self):
        """Remove the second stop key (then Esc can be recorded into a macro)."""
        if self.settings.hotkey_stop:
            self._set("hotkey_stop", "")
            self._keys_changed()
            self.flash(tr("msg_stop_cleared"))

    def _reset_keys(self):
        for field, key in HOTKEY_DEFAULTS.items():
            self._set(field, key)
        self._keys_changed()
        self.flash(tr("msg_keys_reset"))

    def on_hotkey(self, name):
        s = self.settings
        if self._capture_target is not None:
            return
        if name == s.hotkey_panic or (s.hotkey_stop and name == s.hotkey_stop):
            self.panic()
        elif name == s.hotkey_click:
            self.toggle_clicking()
        elif name == s.hotkey_record:
            self.toggle_recording()
        elif name == s.hotkey_play:
            self.toggle_playback()

    # ================================================================ actions
    def _connect_engine(self):
        e = self.engine
        e.clickerStopped.connect(self._on_worker_stopped, Qt.QueuedConnection)
        e.playerStopped.connect(self._on_worker_stopped, Qt.QueuedConnection)
        e.playerProgress.connect(self._on_progress, Qt.QueuedConnection)
        e.stepRecorded.connect(self._on_step_recorded, Qt.QueuedConnection)
        e.error.connect(self._on_engine_error, Qt.QueuedConnection)

    def _on_engine_error(self, text):
        self.flash(text)
        self._say("error")

    def on_hotkeys_failed(self, text):
        """Hotkeys failed to start: show the reason and suggest the paw button."""
        self.flash(text)
        self._say("no_hotkeys")

    def _on_paw_clicked(self):
        if self.state == "recording":
            self.toggle_recording(from_ui=True)
        elif self.state == "countdown":
            self._cancel_countdown()
        elif self.state != "idle":
            self.panic(user_stop=True)
        elif self.stack.currentIndex() == 1:
            self.toggle_playback(from_ui=True)
        else:
            self.toggle_clicking(from_ui=True)

    def toggle_clicking(self, from_ui=False):
        if self.state == "clicking":
            self._stop_reason = "user"
            self.engine.stop_all()
        elif self.state == "countdown":
            self._cancel_countdown()
        elif self.state == "idle":
            if from_ui:
                self._start_countdown(self._start_clicking)
            else:
                self._start_clicking()

    def _start_clicking(self):
        s = self.settings
        ok = self.engine.start_clicking(
            s.interval_seconds, s.button, s.double_click, None if s.repeat_forever else s.repeat_count)
        self._milestone = 0
        self._stop_reason = None
        self.set_state("clicking" if ok else "idle")
        if ok:
            self._said_mood = "calm"
            self._say("click_start")

    def toggle_recording(self, from_ui=False):
        if self.state == "recording":
            steps = self.engine.stop_recording(drop_last_click_within=1.0 if from_ui else 0.0)
            self.macro.steps = steps
            self._fill_table()
            self.set_state("idle")
            n = len(steps)
            self.sounds.play("record_stop")
            self._macro_changed()
            self.flash(tr("msg_recorded", n=n, word=plural(n, "step"), name=_short(self.current_macro)))
            self._say("record_done", n=n, noun="step")
        elif self.state == "countdown" and self._countdown_action == self._begin_recording:
            self._cancel_countdown()
        elif self.state == "idle":
            self._set_tab(1)
            if self.settings.countdown_record:
                self._start_countdown(self._begin_recording)
            else:
                self._begin_recording()

    def _begin_recording(self):
        s = self.settings
        if self.engine.start_recording(s.record_moves, s.record_keys, excluded_keys=self._app_keys()):
            self.macro.steps = []
            self._fill_table()
            self._set_tab(1)
            self.sounds.play("record_start")
            self.set_state("recording")
            self._say("record_start")
        else:
            self.set_state("idle")

    def toggle_playback(self, from_ui=False):
        if self.state == "playing":
            self._stop_reason = "user"
            self.engine.stop_all()
        elif self.state == "countdown":
            self._cancel_countdown()
        elif self.state == "idle":
            if not self.macro.steps:
                self.flash(tr("msg_empty", key=pretty_key(self.settings.hotkey_record)))
                return
            if from_ui or self.settings.countdown_play:
                self._start_countdown(self._start_playback)
            else:
                self._start_playback()

    def _start_playback(self):
        s = self.settings
        ok = self.engine.start_playback(self.macro, None if s.macro_loop else s.macro_repeat_count,
                                        skip_keys=self._app_keys())
        if ok:
            self.sounds.play("play_start")
        self._stop_reason = None
        self._last_loop = 0
        self._last_loop_said = 0.0
        self.set_state("playing" if ok else "idle")
        if ok:
            self._said_mood = "calm"
            self._say("play_start")

    def panic(self, user_stop=False):
        """Panic stop: stops anything at all.
        user_stop=True is just a "stop" with the big paw; the cat does not get scared."""
        if self.state == "recording":
            self.toggle_recording()
            return
        if self.state == "countdown":
            self._cancel_countdown()
            return
        prev = self.state
        self.engine.stop_all()
        self.set_state("idle")
        if prev in ("clicking", "playing"):
            self._say_stopped(prev, "user" if user_stop else "panic")

    def _on_worker_stopped(self):
        if self.state in ("clicking", "playing"):
            prev = self.state
            reason = self._stop_reason or "done"
            self.set_state("idle")
            self._say_stopped(prev, reason)

    def _say_stopped(self, prev, reason):
        self._stop_reason = None
        if reason == "panic":
            self._say("panic")
        elif prev == "clicking":
            n = self.engine.clicks
            self._say("click_stop", n=n if n > 0 else None, noun="click")
        else:
            self._say("play_stop" if reason == "user" else "play_done")

    # --- countdown before starting from the button ---
    def _start_countdown(self, action):
        self._countdown_action = action
        self._countdown_left = COUNTDOWN_SECONDS
        self.set_state("countdown")
        self._say("record_countdown" if action == self._begin_recording else "click_countdown")
        # ONE sound for all 3 seconds (beep, beep, beep); a custom sound plays once and is cut at 3 s
        self.sounds.play("countdown")
        self._countdown_timer.start()

    def _countdown_tick(self):
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown_timer.stop()
            action, self._countdown_action = self._countdown_action, None
            self.state = "idle"
            if action:
                action()
        else:
            self.set_state("countdown")       # only the digit on the paw; the sound is already playing since the countdown started

    def _cancel_countdown(self):
        self._countdown_timer.stop()
        self._countdown_action = None
        self.sounds.stop()                    # cancel: the beeps stop at once
        self.set_state("idle")

    # ================================================================ state / texts
    def set_state(self, state):
        if state != self.state:
            self._phrase = ""          # the phrase belongs to the previous state: forget it
        self.state = state
        self.cat.set_state("idle" if state == "countdown" else state)
        if state == "recording":
            if not self._tick_timer.isActive():
                self._tick_timer.start()
        else:
            self._tick_timer.stop()
        if state != "idle":
            self.promo_toast.dismiss()   # the cat is busy: do not distract
        self.mouse_mascot.set_state("recording" if state == "recording" else "idle")
        busy = state != "idle"
        caption = {"idle": tr("paw_start"), "countdown": str(self._countdown_left)}.get(state, tr("paw_stop"))
        self.paw.set_active(state in ("clicking", "playing", "recording"), caption)
        self.simple_page.setEnabled(not busy)
        self.lang_seg.setEnabled(not busy)
        for b in self.tab_buttons:
            b.setEnabled(not busy)
        for w in self.edit_buttons + [self.btn_new, self.btn_more, self.macro_combo,
                                      self.key_record, self.key_play, self.record_moves,
                                      self.record_keys, self.macro_repeat_seg, self.settings_page]:
            w.setEnabled(not busy)
        self.macro_repeat.setEnabled(not busy and not self.settings.macro_loop)
        self.key_panic.setEnabled(not busy)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers if busy else EDIT_TRIGGERS)
        rec = state == "recording"
        self.btn_record.setEnabled(state in ("idle", "recording")
                                   or (state == "countdown" and self._countdown_action == self._begin_recording))
        self.btn_record.setProperty("recording", "true" if rec else "false")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self._refresh_texts()
        self._schedule_chat()

    def _refresh_texts(self):
        s = self.settings
        keys = self._key_kw()
        title, lore = STATUS.get(self.state, STATUS["idle"])
        if self.state == "idle" and self.stack.currentIndex() == 1:
            lore = "st_idle_lore_macro"
        if self.state == "countdown" and self._countdown_action == self._begin_recording:
            title, lore = "st_countdown_rec", "st_countdown_rec_lore"
        mood = self.cat.mood.state
        if self._effective_mood() in MOOD_STATUS:
            title, lore = MOOD_STATUS[mood]
        self.status_title.setText(nbsp(tr(title, **keys)))
        flash = self._flash_text
        if len(flash) > FLASH_MAX:
            self.status_lore.setToolTip(flash)
            flash = flash[:FLASH_MAX - 1].rstrip() + "…"
        else:
            self.status_lore.setToolTip("")
        # important message > cat phrase > normal hint
        if flash:
            text = flash
        elif s.chatty and self._phrase and self._phrase_state == self.state:
            text = self._phrase
        else:
            text = tr(lore, **keys)
        self.status_lore.setText(nbsp(text))      # nice wrapping: short words never hang at the end of a line
        self.hint.setText(nbsp(tr("hint_macro" if self.stack.currentIndex() == 1 else "hint_simple", **keys)))
        self.btn_record.setText(tr("rec_stop" if self.state == "recording" else "rec_start", key=keys["record"]))

    def flash(self, text):
        """A short message in the cat's "bubble"."""
        self._flash_text = " ".join(str(text).split())
        self._refresh_texts()
        self._flash_timer.start()

    def _clear_flash(self):
        self._flash_text = ""
        self._refresh_texts()

    # ================================================================ chatty cat
    def _effective_mood(self):
        """The mood that is actually shown (taking disabled animations and disco into account)."""
        s = self.settings
        mood = self.cat.mood.state
        if self.state not in ("clicking", "playing") or not s.anim_enabled or mood not in MOOD_STATUS:
            return "calm"
        if mood == "disco" and not s.anim_disco:
            return "hyper"
        return mood

    def _num(self, n):
        sep = " " if i18n.language() == "ru" else ","
        return f"{n:,}".replace(",", sep)

    def _say(self, situation, n=None, noun=None, fade=False, **kw):
        """The cat says a phrase from phrases.py (if "Chatty cat" is on).
        The phrase replaces the normal hint until the state changes."""
        if not self.settings.chatty:
            return
        fmt = dict(kw)
        if n is not None:
            fmt["n"] = self._num(n)
            fmt["w"] = plural(n, noun) if noun else ""
        text = self.phrases.pick(situation, i18n.language(), **fmt)
        if not text:
            return
        self._phrase = text
        self._phrase_state = self.state
        self._phrase_ctx = (situation, n, noun, kw)
        self._refresh_texts()
        if fade and not self._flash_text:
            self._fade_in_lore()
        self._schedule_chat()

    def _fade_in_lore(self):
        """A gentle fade-in of a new phrase (no flicker). Immediately if animations are off."""
        if not self.settings.anim_enabled:
            return
        eff = QGraphicsOpacityEffect(self.status_lore)
        self.status_lore.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(450)
        anim.setStartValue(0.15)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: self.status_lore.setGraphicsEffect(None))
        anim.start()
        self._fade_anim = anim

    def _chat_situation(self):
        """What the cat may say "just because" in the current state (or None: stay quiet)."""
        if self.state == "idle":
            return "idle"
        if self.state == "recording":
            return "recording"
        if self.state == "clicking" and self._effective_mood() == "calm":
            return "clicking"
        return None

    def _schedule_chat(self):
        self._chat_timer.stop()
        rng = CHAT_EVERY.get(self.state)
        if self.settings.chatty and rng:
            self._chat_timer.start(int(random.uniform(*rng) * 1000))

    def _chat_tick(self):
        situation = self._chat_situation()
        if not self.settings.chatty or situation is None:
            return
        # window minimised, an important message is shown or a key capture is pending: no chatter, check later
        if (not self.isVisible() or self.isMinimized() or self._flash_text
                or self._capture_target is not None or self.promo_toast.isVisible()):
            self._chat_timer.start(5000)
            return
        self._say(situation, fade=True)

    def _on_mood(self, _mood):
        mood = self._effective_mood()
        if mood != self._said_mood and self.state in ("clicking", "playing"):
            prev, self._said_mood = self._said_mood, mood
            if mood in MOOD_STATUS:
                self._say(mood)
            elif prev != "calm" and self.state == "clicking":
                self._say("clicking")
            else:
                self._phrase = ""
        self._refresh_texts()
        self._schedule_chat()

    def _set_chatty(self, on):
        self._set("chatty", on)
        if not on:
            self._phrase = ""
            self._chat_timer.stop()
        self._refresh_texts()
        self._schedule_chat()

    def _update_counter(self):
        cur = (self.engine.clicks, self.engine.total_clicks)
        if cur == self._last_counter:
            return
        self._last_counter = cur
        n, total = cur
        self.counter.setText(tr("counter", n=self._num(n), total=self._num(total)))
        if self.state == "clicking":
            m = milestone_reached(n, self._milestone)
            if m:
                self._milestone = m
                self._say("milestone", n=m, noun="click")

    # ================================================================ steps table
    def _fill_table(self):
        self._filling_table = True
        self.table.setRowCount(len(self.macro.steps))
        for row, step in enumerate(self.macro.steps):
            self._fill_row(row, step)
        self._filling_table = False
        self._update_stats()

    def _fill_row(self, row, step: Step):
        was = self._filling_table
        self._filling_table = True
        ro = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        rw = ro | Qt.ItemIsEditable

        n = QTableWidgetItem(str(row + 1))
        n.setFlags(ro)
        n.setForeground(QColor(theme.FAINT))
        mark = {"click": "●  ", "move": "→  ", "wait": "‖  ", "key": "⌨  ",
                "mouse_down": "▼  ", "mouse_up": "▲  ", "scroll": "↕  "}[step.kind]
        act = QTableWidgetItem(mark + step.describe())
        act.setFlags(ro)
        act.setForeground(QColor({"click": theme.ORANGE_SOFT, "mouse_down": theme.ORANGE_SOFT,
                                  "mouse_up": theme.ORANGE_SOFT, "move": theme.MUTED,
                                  "key": theme.GREEN}.get(step.kind, theme.PURPLE)))
        self.table.setItem(row, COL_N, n)
        self.table.setItem(row, COL_ACT, act)
        for col, val in ((COL_X, step.x), (COL_Y, step.y)):
            it = QTableWidgetItem()
            if step.kind in ("wait", "key"):
                it.setText("—")
                it.setFlags(ro)
                it.setForeground(QColor(theme.FAINT))
            else:
                it.setData(Qt.EditRole, int(val))
                it.setFlags(rw)
            self.table.setItem(row, col, it)
        d = QTableWidgetItem()
        d.setData(Qt.EditRole, int(step.delay_ms))
        d.setFlags(rw)
        d.setForeground(QColor(theme.TEXT))
        self.table.setItem(row, COL_DELAY, d)
        self._filling_table = was

    def _on_item_changed(self, item):
        if self._filling_table:
            return
        row, col = item.row(), item.column()
        if not (0 <= row < len(self.macro.steps)):
            return
        step = self.macro.steps[row]
        try:
            value = int(item.data(Qt.EditRole))
        except (TypeError, ValueError):
            self._fill_row(row, step)
            return
        if col == COL_X:
            step.x = value
        elif col == COL_Y:
            step.y = value
        elif col == COL_DELAY:
            step.delay_ms = max(0, value)
            if value < 0:
                self._fill_row(row, step)
        self._update_stats()

    def _on_table_double_clicked(self, index):
        if self.state != "idle" or index.column() not in (COL_N, COL_ACT):
            return
        row = index.row()
        if self.macro.steps[row].kind == "key":
            self.flash(tr("msg_key_step_edit"))
            return
        dlg = StepDialog(self.macro.steps[row], self.engine.cursor_position, self)
        if dlg.exec():
            self.macro.steps[row] = dlg.result_step()
            self._fill_row(row, self.macro.steps[row])
            self._update_stats()

    def _on_step_recorded(self, step):
        if self.state != "recording":
            return
        if self.macro.steps and self.macro.steps[-1] is step:
            # the same step sent again (wheel notches were added to it): refresh its row
            self._fill_row(len(self.macro.steps) - 1, step)
            return
        self.macro.steps.append(step)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._fill_row(row, step)
        self.table.scrollToBottom()
        self._update_stats()

    def _on_progress(self, idx, loop):
        if self.state == "playing" and 0 <= idx < self.table.rowCount():
            self.table.selectRow(idx)
        if self.state == "playing" and loop > self._last_loop:
            self._last_loop = loop          # loop = how many full loops are done
            now = time.monotonic()
            if (loop == 1 or loop % 10 == 0) and now - self._last_loop_said >= LOOP_PHRASE_GAP:
                self._last_loop_said = now
                self._say("play_loop", n=loop, noun="lap")

    def _selected_rows(self):
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _insert_step(self, step):
        rows = self._selected_rows()
        pos = rows[-1] + 1 if rows else len(self.macro.steps)
        self.macro.steps.insert(pos, step)
        self._fill_table()
        self.table.selectRow(pos)

    def _add_click_step(self):
        pos = self.engine.cursor_position() or (0, 0)
        dlg = StepDialog(Step(kind="click", x=pos[0], y=pos[1], delay_ms=300), self.engine.cursor_position, self)
        if dlg.exec():
            self._insert_step(dlg.result_step())

    def _add_wait_step(self):
        self._insert_step(Step(kind="wait", delay_ms=500))

    def _delete_steps(self):
        rows = self._selected_rows()
        if not rows:
            self.flash(tr("msg_select_rows"))
            return
        for r in reversed(rows):
            del self.macro.steps[r]
        self._fill_table()
        if self.macro.steps:
            self.table.selectRow(min(rows[0], len(self.macro.steps) - 1))

    def _move_step(self, delta):
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        r = rows[0]
        t = r + delta
        if 0 <= t < len(self.macro.steps):
            s = self.macro.steps
            s[r], s[t] = s[t], s[r]
            self._fill_table()
            self.table.selectRow(t)

    def _ask(self, text) -> bool:
        """A "yes / no" question with buttons in the current language."""
        box = QMessageBox(QMessageBox.Question, tr("app_title"), text, parent=self)
        yes = box.addButton(tr("yes"), QMessageBox.YesRole)
        box.addButton(tr("no"), QMessageBox.NoRole)
        box.exec()
        return box.clickedButton() is yes

    def _clear_steps(self):
        if not self.macro.steps:
            return
        if self._ask(tr("ask_clear")):
            self.macro.steps = []
            self._fill_table()

    def _update_stats(self):
        m = self.macro
        clicks, keys, steps = m.click_count, m.key_count, len(m.steps)
        secs = f"{m.duration_ms / 1000:.1f}"
        if i18n.language() == "ru":
            secs = secs.replace(".", ",")
        self._macro_changed()
        self.macro_stats.setText(tr("stats", clicks=clicks, clicks_w=plural(clicks, "click"),
                                    keys=keys, keys_w=plural(keys, "key"),
                                    steps=steps, steps_w=plural(steps, "step"), secs=secs))

    # ================================================================ macro library
    def _init_library(self):
        """First run with the library: migrate the old autosave and old files, then open a macro."""
        st = self.settings
        if not st.library_migrated:
            old_dirs = [paths.macros_dir()]      # the old default "Save..." folder
            self.library.migrate(paths.config_dir() / AUTOSAVE_NAME, old_dirs, autosave_name=tr("default_macro"))
            self._set("library_migrated", True)
        names = self.library.names()
        if not names:
            names = [self.library.create(tr("default_macro"))]
        name = st.current_macro if st.current_macro in names else names[0]
        self._switch_macro(name)

    def _reload_combo(self):
        self.macro_combo.blockSignals(True)
        self.macro_combo.clear()
        for n in self.library.names():
            self.macro_combo.addItem(n)
        idx = self.macro_combo.findText(self.current_macro, Qt.MatchExactly)
        self.macro_combo.setCurrentIndex(max(0, idx))
        self.macro_combo.blockSignals(False)

    def _switch_macro(self, name):
        """Save the current macro and open another one from the library."""
        self._flush_macro()
        try:
            macro = self.library.load(name)
        except (OSError, ValueError, TypeError) as exc:
            self.flash(tr("msg_open_fail", err=exc))
            macro = Macro(name=name)
        self.current_macro = name
        self._set_macro(macro)
        self._reload_combo()
        if self.settings.current_macro != name:
            self._set("current_macro", name)

    def _set_macro(self, macro: Macro):
        self.macro = macro
        self._loading_macro = True
        try:
            self._fill_table()
        finally:
            self._loading_macro = False

    def _macro_changed(self):
        """Any edit of the steps is saved to the macro file (with a short delay)."""
        if not self._loading_macro and self.current_macro and self.state != "recording":
            self._macro_save_timer.start()

    def _autosave_macro(self):
        if not self.current_macro or self.state == "recording":
            return
        try:
            self.library.save(self.current_macro, self.macro)
        except OSError as exc:
            self.flash(tr("msg_save_fail", err=exc))

    def _flush_macro(self):
        if self._macro_save_timer.isActive():
            self._macro_save_timer.stop()
            self._autosave_macro()

    def _on_macro_chosen(self, idx):
        name = self.macro_combo.itemText(idx)
        if name and name != self.current_macro:
            self._switch_macro(name)

    def _ask_name(self, title, label, text):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(text)
        dlg.setOkButtonText(tr("ok"))
        dlg.setCancelButtonText(tr("cancel"))
        if dlg.exec():
            return dlg.textValue().strip()
        return ""

    def _new_macro(self):
        self._flush_macro()
        name = self.library.create(tr("new_macro"))
        self._switch_macro(name)
        self.flash(tr("msg_created", name=_short(name)))
        self._say("macro_created")

    def _rename_macro(self):
        new = self._ask_name(tr("m_rename").rstrip("…"), tr("ask_rename"), self.current_macro)
        if not new or new == self.current_macro:
            return
        self._flush_macro()
        try:
            self.library.save(self.current_macro, self.macro)
            name = self.library.rename(self.current_macro, new)
        except OSError as exc:
            self.flash(tr("msg_lib_fail", err=exc))
            return
        self.current_macro = name
        self._set("current_macro", name)
        self._reload_combo()
        self.flash(tr("msg_renamed", name=_short(name)))
        self._say("macro_saved")

    def _duplicate_macro(self):
        self._flush_macro()
        try:
            self.library.save(self.current_macro, self.macro)
            name = self.library.duplicate(self.current_macro, tr("copy_name", name=self.current_macro))
        except (OSError, ValueError) as exc:
            self.flash(tr("msg_lib_fail", err=exc))
            return
        self._switch_macro(name)
        self.flash(tr("msg_duplicated", name=_short(name)))
        self._say("macro_created")

    def _delete_macro(self):
        old = self.current_macro
        if not self._ask(tr("ask_delete", name=old)):
            return
        self._macro_save_timer.stop()
        try:
            self.library.delete(old)
        except OSError as exc:
            self.flash(tr("msg_lib_fail", err=exc))
            return
        names = self.library.names() or [self.library.create(tr("default_macro"))]
        self.current_macro = ""
        self._switch_macro(names[0])
        self.flash(tr("msg_deleted", name=_short(old)))
        self._say("macro_deleted")

    def _dialog_dir(self):
        last = self.settings.last_macro
        if last and Path(last).parent.is_dir():
            return Path(last).parent
        return Path.home()

    def _import_macro(self):
        fn, _ = QFileDialog.getOpenFileName(self, tr("dlg_open"), str(self._dialog_dir()), tr("file_filter"))
        if not fn:
            return
        try:
            self._flush_macro()
            name = self.library.import_file(fn)
            self._set("last_macro", fn)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, tr("app_title"), tr("msg_open_fail", err=exc))
            return
        self._switch_macro(name)
        self.flash(tr("msg_opened", name=_short(name)))

    def _export_macro(self):
        safe = "".join(ch for ch in self.current_macro if ch not in '\\/:*?"<>|').strip() or "macro"
        fn, _ = QFileDialog.getSaveFileName(self, tr("dlg_save"), str(self._dialog_dir() / f"{safe}.json"),
                                            tr("file_filter"))
        if not fn:
            return
        if not fn.lower().endswith(".json"):
            fn += ".json"
        try:
            self.macro.save(fn)
            self._set("last_macro", fn)
            self.flash(tr("msg_saved"))
            self._say("macro_saved")
        except OSError as exc:
            QMessageBox.warning(self, tr("app_title"), tr("msg_save_fail", err=exc))

    def _open_library_folder(self):
        # opens the folder in the file manager (a local path, not the internet)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.folder)))

    # ================================================================ "Settings" tab
    def _build_settings_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # The cat: animations, hat, disco, chattiness, in one row
        c, l = _card(margins=(18, 10, 18, 12), spacing=8)
        self._header(l, "paw", "set_cat_title", "set_cat_hint")
        r = QHBoxLayout()
        r.setSpacing(22)
        self.anim_master = Switch()
        self._text(self.anim_master, "anim_master")
        self._text(self.anim_master, "anim_master_tip", "setToolTip")
        self.anim_hat = Switch()
        self._text(self.anim_hat, "anim_hat")
        self._text(self.anim_hat, "anim_hat_tip", "setToolTip")
        self.anim_disco = Switch()
        self._text(self.anim_disco, "anim_disco")
        self._text(self.anim_disco, "anim_disco_tip", "setToolTip")
        for sw, field in ((self.anim_master, "anim_enabled"), (self.anim_hat, "anim_hat"),
                          (self.anim_disco, "anim_disco")):
            sw.toggled.connect(lambda v, f=field: (self._set(f, v), self._apply_anim()))
            r.addWidget(sw)
        # cat phrases do not depend on animations: they can stay on with animations off
        self.chatty = Switch()
        self._text(self.chatty, "anim_chatty")
        self._text(self.chatty, "anim_chatty_tip", "setToolTip")
        self.chatty.toggled.connect(self._set_chatty)
        r.addStretch(1)
        r.addWidget(self.chatty)
        l.addLayout(r)
        lay.addWidget(c)

        cols = QHBoxLayout()
        cols.setSpacing(12)
        cols.addWidget(self._build_hotkeys_card())
        cols.addWidget(self._build_sounds_card(), 1)
        lay.addLayout(cols, 1)
        self.settings_page = page
        return page

    def _build_hotkeys_card(self):
        """Settings -> Hotkeys: all five keys in one place."""
        c, l = _card(margins=(18, 10, 18, 12), spacing=6)
        c.setFixedWidth(272)
        self._header(l, "key", "set_keys_title", "set_keys_hint")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.hk_buttons = {}
        for i, field in enumerate(HOTKEY_DEFAULTS):
            short = field.split("_", 1)[1]                    # hotkey_click -> click
            lbl = self._text(_label("cardHint"), f"hk_{short}")
            btn = KeyCaptureButton(tip_key="keycap_tip_stop" if field == "hotkey_stop" else "keycap_tip")
            btn.setMinimumWidth(108)                          # fits both "CapsLock" and "Shift (R)"
            btn.captureRequested.connect(self._begin_capture)
            self.hk_buttons[btn] = field
            grid.addWidget(lbl, i, 0)
            grid.addWidget(btn, i, 1)
            if field == "hotkey_stop":
                self._text(lbl, "hk_stop_tip", "setToolTip")
                self.hk_clear = QPushButton("×")
                self.hk_clear.setObjectName("small")
                self.hk_clear.setFixedWidth(30)
                self.hk_clear.setCursor(Qt.PointingHandCursor)
                self._text(self.hk_clear, "hk_clear_tip", "setToolTip")
                self.hk_clear.clicked.connect(self._clear_stop_key)
                grid.addWidget(self.hk_clear, i, 2)
        grid.setColumnStretch(0, 1)
        l.addLayout(grid)
        l.addStretch(1)
        reset = self._text(QPushButton(), "hk_reset")
        reset.setObjectName("small")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._reset_keys)
        l.addWidget(reset, 0, Qt.AlignLeft)
        return c

    def _build_sounds_card(self):
        c, l = _card(margins=(18, 10, 18, 12), spacing=6)
        row, t, h = card_header("sound")
        self._text(t, "set_sound_title")
        self._tr(lambda: h.setText(nbsp(tr("set_sound_hint" if media_supported() else "set_sound_hint_wav"))))
        l.addLayout(row)
        vol = QHBoxLayout()
        vol.setSpacing(10)
        vol.addWidget(self._text(_label("cardHint"), "volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(160)
        self.volume.setCursor(Qt.PointingHandCursor)
        self.volume_label = _label("cardTitle")
        self.volume_label.setFixedWidth(46)
        self.volume.valueChanged.connect(self._on_volume)
        self.volume.sliderReleased.connect(lambda: self.sounds.play("countdown", preview=True))
        vol.addWidget(self.volume)
        vol.addWidget(self.volume_label)
        vol.addStretch(1)
        l.addLayout(vol)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.sound_switches, self.sound_files = {}, {}
        for i, ev in enumerate(EVENTS):
            sw = Switch()
            self._text(sw, f"snd_{ev}")
            sw.toggled.connect(lambda v, e=ev: self._set(f"sound_{e}", v))
            file_lbl = _label("soundFile")
            file_lbl.setMinimumWidth(60)
            play = QPushButton("▶")
            play.setObjectName("play")
            self._text(play, "snd_preview_tip", "setToolTip")
            play.clicked.connect(lambda _=False, e=ev: self._preview_sound(e))
            pick = self._text(QPushButton(), "snd_custom")
            pick.setObjectName("small")
            pick.clicked.connect(lambda _=False, e=ev: self._pick_sound(e))
            reset = self._text(QPushButton(), "snd_reset")
            reset.setObjectName("small")
            reset.clicked.connect(lambda _=False, e=ev: self._reset_sound(e))
            for b in (play, pick, reset):
                b.setCursor(Qt.PointingHandCursor)
            grid.addWidget(sw, i, 0)
            grid.addWidget(file_lbl, i, 1)
            grid.addWidget(play, i, 2)
            grid.addWidget(pick, i, 3)
            grid.addWidget(reset, i, 4)
            self.sound_switches[ev] = sw
            self.sound_files[ev] = (file_lbl, reset)
        grid.setColumnStretch(1, 1)
        l.addLayout(grid)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {theme.BORDER};")
        l.addSpacing(2)
        l.addWidget(sep)
        self.cd_record = Switch()
        self._tr(lambda: self.cd_record.setText(tr("cd_record", n=COUNTDOWN_SECONDS)))
        self._text(self.cd_record, "cd_record_tip", "setToolTip")
        self.cd_record.toggled.connect(lambda v: self._set("countdown_record", v))
        self.cd_play = Switch()
        self._tr(lambda: self.cd_play.setText(tr("cd_play", n=COUNTDOWN_SECONDS)))
        self._text(self.cd_play, "cd_play_tip", "setToolTip")
        self.cd_play.toggled.connect(lambda v: self._set("countdown_play", v))
        l.addWidget(self.cd_record)       # one under the other: long labels
        l.addWidget(self.cd_play)
        l.addStretch(1)
        return c

    def _apply_anim(self):
        """Master animation switch: when off, everything stands still:
        the cat, the mouse, the paw, the bubble, the switches. Hat and disco are greyed out then."""
        s = self.settings
        on = s.anim_enabled
        self.anim_hat.setEnabled(on)
        self.anim_disco.setEnabled(on)
        set_ui_animations(on)
        self.cat.set_options(on, s.anim_hat, s.anim_disco)
        self.mouse_mascot.set_animated(on)
        self.paw.set_active(self.paw._active, self.paw.caption)
        self.promo_toast.animated = on
        if not on and self._fade_anim is not None:
            self._fade_anim.stop()
            self.status_lore.setGraphicsEffect(None)
            self._fade_anim = None
        self._refresh_texts()

    def _on_volume(self, v):
        self.volume_label.setText(f"{v}%")
        was = self.settings.sound_volume
        self._set("sound_volume", int(v))
        if v == 0 and was > 0:
            self._say("sound_muted")

    def _refresh_sound_files(self):
        if not hasattr(self, "sound_files"):
            return
        for ev, (lbl, reset) in self.sound_files.items():
            custom = self.sounds.custom(ev)
            if custom:
                name = Path(custom).name
                if not Path(custom).is_file():
                    lbl.setText(tr("snd_missing", name=name))
                elif custom in self.sounds.broken:
                    lbl.setText(tr("snd_broken", name=name))
                else:
                    lbl.setText(name)
                lbl.setToolTip(custom)
            else:
                lbl.setText(tr("snd_default"))
                lbl.setToolTip("")
            reset.setEnabled(bool(custom))
            # long file names are elided with "..." so they do not widen the row
            fm = lbl.fontMetrics()
            lbl.setText(fm.elidedText(lbl.text(), Qt.ElideMiddle, 200))

    def _preview_sound(self, event):
        path = self.sounds.path_for(event)
        if path != default_path(event) and needs_media(path):
            media = self.sounds.media_backend()   # MP3 and the like are played by QMediaPlayer
            silent = media is not None and media.name == "none"
        else:
            silent = self.sounds.backend.name == "none"
        if silent:
            self.flash(tr("msg_no_audio"))
            return
        self.sounds.play(event, preview=True)

    def _on_sound_error(self, event, path, reason):
        """A custom sound does not play: say so; the default sound is already playing instead."""
        if reason == "no_media":
            self.flash(tr("msg_no_media"))
        else:
            self.flash(tr("msg_bad_sound", name=_short(Path(path).name)))
        self._refresh_sound_files()

    def _pick_sound(self, event):
        start = self.sounds.custom(event) or str(Path.home())
        media = media_supported()
        fn, _ = QFileDialog.getOpenFileName(self, tr("dlg_sound"), start,
                                            tr("sound_filter" if media else "sound_filter_wav"))
        if not fn:
            return
        if check_sound(fn):     # "" = all good, otherwise the reason
            self.flash(tr("msg_bad_format" if media else "msg_bad_wav", name=_short(Path(fn).name)))
            return
        fn = self._offer_trim(event, fn)
        if not fn:
            return                      # "Cancel" in the trim dialog
        self.sounds.forget(fn)
        custom = dict(self.settings.sound_custom)
        custom[event] = fn
        self._set("sound_custom", custom)
        self._refresh_sound_files()
        self.sounds.play(event, preview=True)

    def _run_trim_dialog(self, dlg):
        """A separate method so tests can "press" the button without a real dialog."""
        return dlg.exec()

    def _offer_trim(self, event, fn):
        """The "Trim sound" dialog. Returns the path to remember, or "" for cancel.
        A saved piece is a new WAV in the sounds_custom folder (the original is not needed afterwards)."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            pcm = load_pcm(fn)
        except TrimError as exc:
            QApplication.restoreOverrideCursor()
            self.flash(tr("msg_trim_fail", err=exc))     # could not read it: use the file as is
            return fn
        QApplication.restoreOverrideCursor()
        dlg = TrimDialog(fn, pcm, tr(f"snd_{event}"), max_seconds_for(event),
                         volume=self.settings.sound_volume / 100, parent=self)
        self._run_trim_dialog(dlg)
        if dlg.choice is None:
            return ""
        if dlg.choice == "nocut":
            return fn
        try:
            out = save_trimmed(pcm, dlg.start, dlg.end, paths.sounds_custom_dir(), event, fn)
        except TrimError as exc:
            self.flash(tr("msg_trim_fail", err=exc))
            return fn
        self.flash(tr("msg_trimmed", name=_short(out.name)))
        return str(out)

    def _reset_sound(self, event):
        custom = dict(self.settings.sound_custom)
        custom.pop(event, None)
        self._set("sound_custom", custom)
        self._refresh_sound_files()

    # ================================================================ Telegram bot bubble
    def _check_promo(self):
        if not self.settings.promo_enabled:
            return
        busy = self.state != "idle" or self._capture_target is not None
        if self.promo.check(time.monotonic(), busy):
            self.show_promo()

    def _on_cat_clicked(self):
        """A click on the cat: it hops a little (if animations are on).
        10 quick clicks in a row: the cat tells about the Telegram bot itself (at most once per 10 minutes)."""
        self.cat.poke()
        now = time.monotonic()
        if not self.egg.click(now):
            return
        if self.state != "idle" or not self.settings.promo_enabled:
            self.egg.last_shown = None     # the cat is busy: do not count it as shown
            return
        self.show_promo()
        self.promo.postpone(now)           # the scheduled bubble will not come right after

    def show_promo(self):
        """The cat "speaks" in its bubble; the window is not activated and focus is not touched."""
        t = self.promo_toast
        pos = self.bubble.mapTo(self.centralWidget(), QPoint(0, 0))
        t.setFixedWidth(self.bubble.width())
        t.setMinimumHeight(self.bubble.height())
        t.adjustSize()
        t.move(pos.x(), pos.y() + (self.bubble.height() - t.height()) // 2)
        t.popup()

    # ================================================================ closing
    def closeEvent(self, event):
        if self.engine.recording:
            self.macro.steps = self.engine.stop_recording()
            self.state = "idle"
        self._countdown_timer.stop()
        self._tick_timer.stop()
        self.engine.stop_all()
        self.hotkeys.stop()
        self._macro_save_timer.stop()
        self._autosave_macro()
        self._save_settings()
        super().closeEvent(event)
