"""The "add / edit step" dialog for the mouse's notebook.

Step types: click, move, pause, hold a button (mouse_down), release it (mouse_up)
and a mouse wheel turn (scroll). Key steps are not edited here (only their delay, in the table)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout)

from ..i18n import tr
from ..macro import BUTTON_KINDS, POSITIONAL, Step
from .widgets import Segmented, Switch


class StepDialog(QDialog):
    def __init__(self, step: Step, cursor_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        self._cursor_fn = cursor_fn
        self._countdown = 0
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self._tick)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)
        title = QLabel(tr("dlg_head"))
        title.setObjectName("cardTitle")
        lay.addWidget(title)

        self.kind = Segmented([("click", tr("dlg_click")), ("mouse_down", tr("dlg_down")),
                               ("mouse_up", tr("dlg_up")), ("scroll", tr("dlg_scroll")),
                               ("move", tr("dlg_move")), ("wait", tr("dlg_wait"))])
        self.kind.set_value(step.kind)
        self.kind.changed.connect(self._sync)
        lay.addWidget(self.kind)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.button = Segmented([("left", tr("btn_left")), ("right", tr("btn_right")), ("middle", tr("btn_middle"))])
        self.button.set_value(step.button)
        self.double = Switch(tr("dlg_double"))
        self.double.setChecked(step.double)
        self.x = QSpinBox(minimum=-20000, maximum=20000, value=step.x)
        self.y = QSpinBox(minimum=-20000, maximum=20000, value=step.y)
        self.delay = QSpinBox(minimum=0, maximum=3_600_000, value=step.delay_ms, suffix=tr("suffix_ms"), singleStep=50)
        # wheel notches: positive dx = right, positive dy = up (like pynput)
        self.dx = QSpinBox(minimum=-100, maximum=100, value=step.dx, prefix="↔ ")
        self.dy = QSpinBox(minimum=-100, maximum=100, value=step.dy, prefix="↕ ")
        for sb in (self.x, self.y, self.delay, self.dx, self.dy):
            sb.setButtonSymbols(QSpinBox.NoButtons)

        self.lbl_button = QLabel(tr("dlg_button"))
        self.lbl_xy = QLabel(tr("dlg_xy"))
        self.lbl_wheel = QLabel(tr("dlg_wheel"))
        for w in (self.lbl_wheel, self.dx, self.dy):
            w.setToolTip(tr("dlg_wheel_tip"))
        grid.addWidget(self.lbl_button, 0, 0)
        grid.addWidget(self.button, 0, 1, 1, 2)
        grid.addWidget(self.double, 1, 1, 1, 2)
        grid.addWidget(self.lbl_xy, 2, 0)
        grid.addWidget(self.x, 2, 1)
        grid.addWidget(self.y, 2, 2)
        grid.addWidget(self.lbl_wheel, 3, 0)
        grid.addWidget(self.dx, 3, 1)
        grid.addWidget(self.dy, 3, 2)
        grid.addWidget(QLabel(tr("dlg_delay")), 4, 0)
        grid.addWidget(self.delay, 4, 1, 1, 2)
        lay.addLayout(grid)

        self.pick = QPushButton(tr("dlg_pick"))
        self.pick.setCursor(Qt.PointingHandCursor)
        self.pick.setToolTip(tr("dlg_pick_tip"))
        self.pick.clicked.connect(self._start_pick)
        lay.addWidget(self.pick)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("cancel"))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(tr("ok"))
        ok.setObjectName("accent")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self._sync()

    def _sync(self, *_):
        kind = self.kind.value()
        pos_on = kind in POSITIONAL
        for w in (self.x, self.y, self.lbl_xy, self.pick):
            w.setEnabled(pos_on)
        for w in (self.button, self.lbl_button):
            w.setEnabled(kind in BUTTON_KINDS)
        self.double.setEnabled(kind == "click")
        for w in (self.dx, self.dy, self.lbl_wheel):
            w.setEnabled(kind == "scroll")

    def _start_pick(self):
        self._countdown = 3
        self.pick.setText(tr("dlg_pick_wait", n=3))
        self._timer.start()

    def _tick(self):
        self._countdown -= 1
        if self._countdown > 0:
            self.pick.setText(tr("dlg_pick_wait", n=self._countdown))
            return
        self._timer.stop()
        pos = self._cursor_fn()
        if pos:
            self.x.setValue(pos[0])
            self.y.setValue(pos[1])
            self.pick.setText(tr("dlg_pick_done", x=pos[0], y=pos[1]))
        else:
            self.pick.setText(tr("dlg_pick_fail"))

    def result_step(self) -> Step:
        kind = self.kind.value()
        return Step(kind=kind, x=self.x.value(), y=self.y.value(),
                    button=self.button.value() or "left", delay_ms=self.delay.value(),
                    double=self.double.isChecked() and kind == "click",
                    dx=self.dx.value() if kind == "scroll" else 0,
                    dy=self.dy.value() if kind == "scroll" else 0)
