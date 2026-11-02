"""Hand-drawn widgets: the paw button, the animated cat, switches."""
import math
import random

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from . import theme
from ..i18n import tr


# Master switch for the "living" UI details (smooth switch, paw pulse, mouse breathing).
# The window sets it from the "Cat animations" setting.
_ui_anim = {"on": True}


def set_ui_animations(on: bool):
    _ui_anim["on"] = bool(on)


def ui_animations() -> bool:
    return _ui_anim["on"]


def add_shadow(widget, blur=28, dy=6, alpha=110):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


def draw_paw(p: QPainter, center: QPointF, size: float, color: QColor):
    """A cat paw: a big pad and four toes."""
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    cx, cy, s = center.x(), center.y(), size
    # main pad: a heart-like trapezoid made of a rounded path
    pad = QPainterPath()
    pad.addRoundedRect(QRectF(cx - s * 0.30, cy - s * 0.02, s * 0.60, s * 0.44), s * 0.2, s * 0.2)
    p.drawPath(pad)
    p.drawEllipse(QPointF(cx - s * 0.16, cy + s * 0.05), s * 0.17, s * 0.15)
    p.drawEllipse(QPointF(cx + s * 0.16, cy + s * 0.05), s * 0.17, s * 0.15)
    # toes
    for dx, dy, r in ((-0.36, -0.20, 0.11), (-0.13, -0.38, 0.12), (0.13, -0.38, 0.12), (0.36, -0.20, 0.11)):
        p.drawEllipse(QPointF(cx + s * dx, cy + s * dy), s * r * 0.9, s * r * 1.1)
    p.restore()


def draw_sparkle(p: QPainter, center: QPointF, r: float, color: QColor):
    """A four-pointed sparkle star."""
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    path = QPainterPath()
    cx, cy, k = center.x(), center.y(), r * 0.28
    path.moveTo(cx, cy - r)
    path.quadTo(cx + k * 0.3, cy - k * 0.3, cx + r, cy)
    path.quadTo(cx + k * 0.3, cy + k * 0.3, cx, cy + r)
    path.quadTo(cx - k * 0.3, cy + k * 0.3, cx - r, cy)
    path.quadTo(cx - k * 0.3, cy - k * 0.3, cx, cy - r)
    p.drawPath(path)
    p.restore()


def draw_note(p: QPainter, pos: QPointF, size: float, color: QColor, double: bool = False):
    """A music note (single or double) drawn with shapes, so it does not depend on the font."""
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    x, y, s = pos.x(), pos.y(), size
    heads = [QPointF(x, y)] + ([QPointF(x + s * 0.75, y - s * 0.18)] if double else [])
    for h in heads:
        p.save()
        p.translate(h)
        p.rotate(-22)
        p.drawEllipse(QPointF(0, 0), s * 0.26, s * 0.19)
        p.restore()
    pen = QPen(color, max(1.2, s * 0.09), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    for h in heads:
        p.drawLine(QPointF(h.x() + s * 0.22, h.y() - s * 0.05), QPointF(h.x() + s * 0.22, h.y() - s * 0.9))
    if double:
        p.drawLine(QPointF(x + s * 0.22, y - s * 0.9), QPointF(x + s * 0.97, y - s * 1.08))
    else:
        p.drawLine(QPointF(x + s * 0.22, y - s * 0.9), QPointF(x + s * 0.5, y - s * 0.62))
    p.restore()


class Card(QFrame):
    """A rounded card with a soft shadow."""

    def __init__(self, parent=None, shadow=True):
        super().__init__(parent)
        self.setObjectName("card")
        if shadow:
            add_shadow(self)


class CardIcon(QWidget):
    """A small icon in a rounded square. kind: key, clock, mouse, repeat, paw, record."""

    def __init__(self, kind: str, parent=None, size: int = 40):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # draw in 44x44 coordinates and scale to the real size
        p.scale(self.width() / 44.0, self.height() / 44.0)
        r = QRectF(1, 1, 42, 42)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 154, 60, 38))
        p.drawRoundedRect(r, 13, 13)
        pen = QPen(QColor(theme.ORANGE), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        c = r.center()
        k = self.kind
        if k == "key":
            p.drawRoundedRect(QRectF(c.x() - 12, c.y() - 8, 24, 16), 4, 4)
            for i in range(3):
                p.drawPoint(QPointF(c.x() - 6 + i * 6, c.y() - 2))
            p.drawLine(QPointF(c.x() - 5, c.y() + 4), QPointF(c.x() + 5, c.y() + 4))
        elif k == "clock":
            p.drawEllipse(c, 11, 11)
            p.drawLine(c, QPointF(c.x(), c.y() - 6))
            p.drawLine(c, QPointF(c.x() + 5, c.y() + 3))
        elif k == "mouse":
            p.drawRoundedRect(QRectF(c.x() - 8, c.y() - 12, 16, 24), 8, 8)
            p.drawLine(QPointF(c.x(), c.y() - 12), QPointF(c.x(), c.y() - 4))
            p.drawLine(QPointF(c.x() - 8, c.y() - 4), QPointF(c.x() + 8, c.y() - 4))
        elif k == "repeat":
            p.drawArc(QRectF(c.x() - 11, c.y() - 9, 22, 18), 30 * 16, 300 * 16)
            p.drawLine(QPointF(c.x() + 9, c.y() - 6), QPointF(c.x() + 11, c.y() - 1))
            p.drawLine(QPointF(c.x() + 11, c.y() - 1), QPointF(c.x() + 5, c.y() - 1))
        elif k == "double":
            p.drawEllipse(c, 4, 4)
            p.drawEllipse(c, 10, 10)
        elif k == "paw":
            draw_paw(p, QPointF(c.x(), c.y() + 3), 22, QColor(theme.ORANGE))
        elif k == "sound":
            body = QPainterPath()
            body.moveTo(c.x() - 11, c.y() - 4)
            body.lineTo(c.x() - 6, c.y() - 4)
            body.lineTo(c.x() + 1, c.y() - 10)
            body.lineTo(c.x() + 1, c.y() + 10)
            body.lineTo(c.x() - 6, c.y() + 4)
            body.lineTo(c.x() - 11, c.y() + 4)
            body.closeSubpath()
            p.drawPath(body)
            p.drawArc(QRectF(c.x() - 3, c.y() - 6, 12, 12), -50 * 16, 100 * 16)
            p.drawArc(QRectF(c.x() - 3, c.y() - 11, 20, 22), -50 * 16, 100 * 16)
        elif k == "sparkle":
            draw_sparkle(p, c, 13, QColor(theme.ORANGE))
            draw_sparkle(p, QPointF(c.x() + 10, c.y() - 9), 5, QColor(theme.ORANGE_SOFT))
        elif k == "record":
            p.setBrush(QColor(theme.RED))
            p.setPen(Qt.NoPen)
            p.drawEllipse(c, 7, 7)


def card_header(icon_kind: str):
    """Card header: icon + title + hint.
    Returns (row, title, hint); the window sets the texts (they need translating)."""
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(CardIcon(icon_kind), 0, Qt.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(1)
    t = QLabel()
    t.setObjectName("cardTitle")
    h = QLabel()
    h.setObjectName("cardHint")
    h.setWordWrap(True)
    col.addWidget(t)
    col.addWidget(h)
    row.addLayout(col, 1)
    return row, t, h


class Segmented(QWidget):
    """A row of buttons, one of which is selected."""

    changed = Signal(str)

    def __init__(self, options, parent=None, object_name="seg", spacing=6):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(spacing)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons = {}
        for value, text in options:
            b = QPushButton(text)
            b.setObjectName(object_name)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            lay.addWidget(b)
            self._buttons[value] = b

    def value(self):
        for v, b in self._buttons.items():
            if b.isChecked():
                return v
        return None

    def set_value(self, value):
        b = self._buttons.get(value)
        if b:
            b.setChecked(True)

    def set_texts(self, texts: dict):
        """New button labels (on language change): {value: text}."""
        for v, text in texts.items():
            if v in self._buttons:
                self._buttons[v].setText(text)

    def buttons(self):
        return list(self._buttons.values())


class KeyCaptureButton(QPushButton):
    """Shows the assigned key; on click waits for a new one."""

    captureRequested = Signal(object)

    def __init__(self, parent=None, tip_key="keycap_tip"):
        super().__init__(parent)
        self.setObjectName("keyCap")
        self.setCursor(Qt.PointingHandCursor)
        self.tip_key = tip_key      # for the "stop" key Esc is a normal key, not "cancel"
        self.setToolTip(tr(tip_key))
        self.key_name = ""
        self._label = ""
        self.clicked.connect(lambda: self.captureRequested.emit(self))

    def set_key(self, name, pretty):
        self.key_name = name
        self._label = pretty
        self.set_capturing(False)

    def retranslate(self, pretty):
        self.setToolTip(tr(self.tip_key))
        self._label = pretty
        self.set_capturing(self.property("capturing") == "true")

    def set_capturing(self, on: bool):
        self.setProperty("capturing", "true" if on else "false")
        self.setText(tr("press_key") if on else self._label)
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()

    def minimumSizeHint(self):
        # a long name ("CapsLock", "Shift (R)") must not be clipped by its neighbours in the row
        return self.sizeHint()


class Switch(QAbstractButton):
    """A "pill" switch with a smooth animation."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=160, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._animate)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, on):
        self._anim.stop()
        if not ui_animations():               # without animations: switch instantly
            self._set_pos(1.0 if on else 0.0)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):  # noqa: N802 - no animation on initial load
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(56 + fm.horizontalAdvance(self.text()) + 6, max(30, fm.height() + 8))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 4, 46, 24)
        off, on = QColor("#4a3834"), QColor(theme.ORANGE)
        col = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(track, 12, 12)
        knob_x = track.left() + 3 + (track.width() - 24) * self._pos
        p.setBrush(QColor("#fff4ea"))
        p.drawEllipse(QRectF(knob_x, track.top() + 3, 18, 18))
        p.setPen(QColor(theme.TEXT if self.isEnabled() else theme.FAINT))
        p.drawText(QRectF(56, 0, self.width() - 56, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class PawButton(QAbstractButton):
    """The big round orange button with a paw. Pulses while the cat is working."""

    def __init__(self, parent=None, size: int = 150):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(size, size)
        self._active = False
        self._pulse = 0.0
        self._hover = False
        self._press = 0.0
        self.caption = ""
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1400)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_pulse)

    def _on_pulse(self, v):
        self._pulse = float(v)
        self.update()

    def set_active(self, active: bool, caption: str):
        self._active = active
        self.caption = caption
        if active and ui_animations():
            if self._anim.state() != QVariantAnimation.Running:
                self._anim.start()
        else:
            self._anim.stop()
            self._pulse = 0.0
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # draw in 176x176 coordinates and scale to the real size
        p.scale(self.width() / 176.0, self.height() / 176.0)
        c = QPointF(88, 88)
        base_r = 62.0
        if self.isDown():
            base_r -= 3

        # soft glow around it
        glow_r = base_r + 22
        glow = QRadialGradient(c, glow_r)
        if not self._active:
            strength = 90
        elif self._anim.state() == QVariantAnimation.Running:
            strength = int(90 + 70 * math.sin(self._pulse * math.pi))
        else:
            strength = 150                    # without animations: just a brighter glow
        animated = self._anim.state() == QVariantAnimation.Running
        glow.setColorAt(0.70, QColor(255, 154, 60, strength))
        glow.setColorAt(1.0, QColor(255, 154, 60, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, glow_r, glow_r)

        # an expanding "wave" ring while active
        if self._active and animated:
            ring_r = base_r + 4 + 22 * self._pulse
            pen = QPen(QColor(255, 184, 119, int(200 * (1 - self._pulse))), 3)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, ring_r, ring_r)

        # the circle itself
        grad = QLinearGradient(c.x(), c.y() - base_r, c.x(), c.y() + base_r)
        top = QColor("#ffc07f") if self._hover else QColor("#ffb066")
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, QColor(theme.ORANGE_DARK))
        p.setPen(QPen(QColor(255, 220, 180, 120), 2))
        p.setBrush(grad)
        p.drawEllipse(c, base_r, base_r)

        # highlight
        hl = QRadialGradient(QPointF(c.x() - 18, c.y() - 30), 40)
        hl.setColorAt(0, QColor(255, 255, 255, 70))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(hl)
        p.drawEllipse(c, base_r - 2, base_r - 2)

        draw_paw(p, QPointF(c.x(), c.y() - 8), 46, QColor("#fff6ec"))

        f = QFont(theme.FONT_FAMILY)
        f.setPixelSize(17)
        f.setWeight(QFont.Black)
        p.setFont(f)
        p.setPen(QColor("#4a230a"))
        p.drawText(QRectF(c.x() - 56, c.y() + 18, 112, 26), Qt.AlignCenter, self.caption)


class MascotView(QWidget):
    """A character with soft "breathing", a light spot and decorations by state.

    state: idle (Zzz), clicking (paw sparkles), recording (red dot), playing (note sparkles).
    """

    def __init__(self, pixmap_path: str, size: int, glow=True, sleepy=True, parent=None):
        super().__init__(parent)
        self._src = QPixmap(pixmap_path)
        self._size = size
        self._glow = glow
        self._sleepy = sleepy
        self._t = 0.0
        self.state = "idle"
        self.setFixedSize(size, size)
        self._sparks = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)  # 25 frames per second: enough and light on the PC
        self._scaled = self._src.scaledToHeight(int(size * 0.86), Qt.SmoothTransformation) if not self._src.isNull() else QPixmap()

    def set_state(self, state):
        self.state = state
        self.update()

    def set_animated(self, on: bool):
        """Without animations: a static picture; the frame timer stops, no sparkles or "breathing"."""
        if on and not self._timer.isActive():
            self._timer.start(40)
        elif not on:
            self._timer.stop()
            self._sparks = []
        self.update()

    @property
    def animating(self) -> bool:
        return self._timer.isActive()

    def _tick(self):
        self._t += 0.04
        if self.state in ("clicking", "playing") and random.random() < 0.25:
            ang = random.uniform(-math.pi, 0)
            self._sparks.append([ang, 0.0, random.uniform(11, 19)])
        self._sparks = [[a, life + 0.035, s] for a, life, s in self._sparks if life < 1.0]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)

        if self._glow:
            col = {"idle": QColor(255, 154, 60, 46), "clicking": QColor(255, 154, 60, 80),
                   "recording": QColor(255, 107, 107, 60), "playing": QColor(155, 122, 224, 70)}[self.state]
            g = QRadialGradient(c, w * 0.5)
            g.setColorAt(0.0, col)
            g.setColorAt(0.65, QColor(col.red(), col.green(), col.blue(), int(col.alpha() * 0.5)))
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, w * 0.5, h * 0.5)
            # the "cushion": a soft shadow under the character
            p.setBrush(QColor(0, 0, 0, 60))
            p.drawEllipse(QPointF(c.x(), h * 0.92), w * 0.30, h * 0.035)

        # breathing: slow, livelier when working
        speed = 1.0 if self.state == "idle" else 3.2
        amp = 0.012 if self.state == "idle" else 0.02
        anim = self._timer.isActive()
        scale = 1.0 + amp * math.sin(self._t * speed * math.pi) if anim else 1.0
        if not self._scaled.isNull():
            pw, ph = self._scaled.width() * scale, self._scaled.height() * scale
            bottom = h * 0.93
            p.drawPixmap(QRectF(c.x() - pw / 2, bottom - ph, pw, ph), self._scaled, QRectF(self._scaled.rect()))

        f = QFont(theme.FONT_FAMILY)
        f.setWeight(QFont.Black)
        if self.state == "idle" and self._sleepy and anim:
            # sleepy "z"s floating up
            for i in range(3):
                ph_ = (self._t * 0.35 + i / 3) % 1.0
                f.setPixelSize(int(12 + 10 * ph_))
                p.setFont(f)
                p.setPen(QColor(255, 210, 170, max(0, int(220 * (1 - ph_)))))
                p.drawText(QPointF(w * 0.74 + 18 * ph_, h * 0.24 - 46 * ph_), "z")
        elif self.state == "recording":
            on = not anim or int(self._t * 2) % 2 == 0
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 107, 107, 230 if on else 90))
            p.drawEllipse(QPointF(w * 0.86, h * 0.12), 7, 7)

        # paw sparkles while working
        for ang, life, s in self._sparks:
            r = w * 0.30 + w * 0.22 * life
            pos = QPointF(c.x() + math.cos(ang) * r, c.y() * 0.95 + math.sin(ang) * r * 0.8)
            col = QColor(theme.ORANGE_SOFT if self.state == "clicking" else theme.PURPLE)
            col.setAlpha(max(0, min(255, int(230 * (1 - life)))))
            draw_paw(p, pos, s, col)


class PawBackground(QWidget):
    """Window background: a warm gradient and barely visible paw prints."""

    def __init__(self, parent=None):
        super().__init__(parent)
        rnd = random.Random(7)  # fixed pattern
        self._paws = [(rnd.random(), rnd.random(), rnd.uniform(14, 26), rnd.uniform(-0.6, 0.6)) for _ in range(26)]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0.0, QColor(theme.BG))
        g.setColorAt(1.0, QColor(theme.BG2))
        p.fillRect(self.rect(), QBrush(g))
        col = QColor(255, 200, 150, 9)
        for x, y, s, rot in self._paws:
            p.save()
            p.translate(x * self.width(), y * self.height())
            p.rotate(math.degrees(rot))
            draw_paw(p, QPointF(0, 0), s, col)
            p.restore()


class ChevronCombo(QComboBox):
    """A combo box with its own check-mark arrow (the standard one is invisible in the dark theme)."""

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(theme.ORANGE if self.isEnabled() else theme.FAINT)
        p.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx, cy = self.width() - 18, self.height() / 2
        p.drawPolyline([QPointF(cx - 5, cy - 2.5), QPointF(cx, cy + 2.5), QPointF(cx + 5, cy - 2.5)])
        p.end()
