"""
The cat on the left and everything around it:
  CatView    - the cat from two pictures (asleep / awake) + the headset "hat" as a separate layer
               that swings on every click; during the disco the cat dances a little.
  DiscoPanel - the left panel; during the "vibe disco" it paints colourful beams, a disco ball,
               sparkles and notes over the background (QPainter only, no video or images).
  PromoToast - the "I have a Telegram bot..." bubble inside the window. It never takes focus,
               and the link opens in the browser only on click.

Performance: clicks send no signals. About 30 times a second the cat looks at the engine's
total counter (a plain number read) and decides by itself how many times to "nod" the hat.
"""
import json
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPixmap,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QWidget)

from .. import paths
from ..reactions import ClickRate, HatWiggle, Mood
from . import theme
from .widgets import draw_note, draw_paw, draw_sparkle

FRAME_MS = 33          # ~30 frames per second while the cat works or dances
IDLE_FRAME_MS = 50     # calm mode (only "Zzz" and breathing)
BEAT_HZ = 2.0          # 120 beats per minute: the disco rhythm


def _load_pivot():
    try:
        with open(paths.asset("cat_layers.json"), encoding="utf-8") as fh:
            px, py = json.load(fh)["pivot"]
            return float(px), float(py)
    except (OSError, ValueError, KeyError, TypeError):
        return 0.47, 0.07


class CatView(QWidget):
    """The cat. state: idle / clicking / recording / playing."""

    moodChanged = Signal(str)
    clicked = Signal()          # a mouse click on the cat (for the easter egg)

    def __init__(self, size: int, click_source=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._click_source = click_source or (lambda: 0)
        h = int(size * 0.86)
        self._pix = {}
        for name in ("sleep", "awake"):
            for layer in ("base", "hat"):
                pm = QPixmap(paths.asset(f"cat_{name}_{layer}.png"))
                self._pix[(name, layer)] = pm.scaledToHeight(h, Qt.SmoothTransformation) if not pm.isNull() else pm
        self._pivot = _load_pivot()
        self.state = "idle"
        self.anim_enabled = True
        self.anim_hat = True
        self.anim_disco = True
        self.rate = ClickRate()
        self.mood = Mood()
        self.wiggle = HatWiggle()
        self.disco_panel = None
        self._t = 0.0
        self._last = time.monotonic()
        self._sparks = []
        self._poke = 0.0            # a "hop" after a click on the cat (1 -> 0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(IDLE_FRAME_MS)

    # --- control ---
    def set_state(self, state):
        self.state = state
        if self._timer.isActive():
            self._timer.setInterval(FRAME_MS if state in ("clicking", "playing") else IDLE_FRAME_MS)
        self.update()

    def set_options(self, enabled: bool, hat: bool, disco: bool):
        """enabled=False means "Cat animations" are off: the frame timer stops and the cat is drawn
        statically (only the asleep / awake picture), with no disco and no hat swing."""
        was = self.anim_enabled
        self.anim_enabled, self.anim_hat, self.anim_disco = bool(enabled), bool(hat), bool(disco)
        if not (enabled and hat):
            self.wiggle.energy = 0.0
        if not enabled:
            self._timer.stop()
            self._sparks = []
            self._poke = 0.0
            if self.mood.state != "calm" or self.mood.intensity > 0:
                self.mood.reset()
                self.moodChanged.emit(self.mood.state)
            if self.disco_panel is not None:
                self.disco_panel.set_level(0.0, self._t)
        elif not was or not self._timer.isActive():
            # turned back on: start counting clicks afresh, without an "accumulated" jump
            self.rate.reset()
            self._last = time.monotonic()
            self._timer.start(FRAME_MS if self.awake else IDLE_FRAME_MS)
        self.update()

    @property
    def animating(self) -> bool:
        """Is a frame-by-frame animation running right now (for tests and debugging)."""
        return self._timer.isActive()

    def poke(self):
        """The cat was poked with the mouse: a small hop and a hat nod (only with animations on)."""
        if not self.anim_enabled:
            return
        self._poke = 1.0
        if self.anim_hat:
            self.wiggle.kick(1)
        self._timer.setInterval(FRAME_MS)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    @property
    def awake(self) -> bool:
        return self.state in ("clicking", "playing")

    @property
    def disco_level(self) -> float:
        return self.mood.intensity if (self.anim_enabled and self.anim_disco) else 0.0

    # --- frame ---
    def _tick(self):
        if not self.anim_enabled:          # just in case: no frames without animations
            self._timer.stop()
            return
        now = time.monotonic()
        dt = max(0.0, min(0.2, now - self._last))
        self._last = now
        self._t += dt
        new = self.rate.feed(int(self._click_source()), now)
        cps = self.rate.cps if self.awake else 0.0
        if self.anim_enabled and self.anim_hat and self.awake:
            self.wiggle.kick(new)
        self.wiggle.step(dt)
        old = self.mood.state
        # the cat stopped: the disco starts fading right away (no cooldown wait)
        self.mood.update(cps, now, disco_allowed=self.anim_enabled and self.anim_disco and self.awake)
        if self.mood.state != old:
            self.moodChanged.emit(self.mood.state)
        if self.awake and random.random() < (0.25 if self.mood.state in ("calm", "lively") else 0.4):
            self._sparks.append([random.uniform(-math.pi, 0), 0.0, random.uniform(11, 19)])
        self._sparks = [[a, life + 0.035, s] for a, life, s in self._sparks if life < 1.0]
        if self.disco_panel is not None:
            self.disco_panel.set_level(self.disco_level, self._t)
        self._poke = max(0.0, self._poke - dt * 2.5)
        busy_anim = self.wiggle.energy > 0 or self.mood.intensity > 0 or self._poke > 0
        self._timer.setInterval(FRAME_MS if (self.awake or busy_anim) else IDLE_FRAME_MS)
        self.update()

    def hat_pose(self):
        if not (self.anim_enabled and self.anim_hat):
            return 0.0, 0.0
        return self.wiggle.pose()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        disco = self.disco_level
        anim = self.anim_enabled          # without animations: a static picture

        col = {"idle": QColor(255, 154, 60, 46), "clicking": QColor(255, 154, 60, 80),
               "recording": QColor(255, 107, 107, 60), "playing": QColor(155, 122, 224, 70)}[self.state]
        if disco > 0:   # during the disco the halo shimmers in all colours
            col = QColor.fromHsvF((self._t * 0.35) % 1.0, 0.65, 1.0, 0.22 + 0.18 * disco)
        g = QRadialGradient(c, w * 0.5)
        g.setColorAt(0.0, col)
        g.setColorAt(0.65, QColor(col.red(), col.green(), col.blue(), int(col.alpha() * 0.5)))
        g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, w * 0.5, h * 0.5)

        # hopping to the beat during the disco
        beat = abs(math.sin(self._t * BEAT_HZ * math.pi))
        bounce = 9.0 * disco * beat + 10.0 * math.sin(self._poke * math.pi)
        squash = 1.0 - 0.035 * disco * (1 - beat)
        p.setBrush(QColor(0, 0, 0, int(60 - 25 * disco * beat)))
        p.drawEllipse(QPointF(c.x(), h * 0.92), w * (0.30 - 0.04 * disco * beat), h * 0.035)

        speed = 1.0 if self.state == "idle" else 3.2
        amp = 0.012 if self.state == "idle" else 0.02
        scale = 1.0 + amp * math.sin(self._t * speed * math.pi) if anim else 1.0
        key = "awake" if self.awake else "sleep"
        base, hat = self._pix[(key, "base")], self._pix[(key, "hat")]
        if not base.isNull():
            pw, ph = base.width() * scale, base.height() * scale * squash
            bottom = h * 0.93 - bounce
            rect = QRectF(c.x() - pw / 2, bottom - ph, pw, ph)
            p.drawPixmap(rect, base, QRectF(base.rect()))
            if not hat.isNull():
                ang, hop = self.hat_pose()
                pivot = QPointF(rect.x() + rect.width() * self._pivot[0], rect.y() + rect.height() * self._pivot[1])
                p.save()
                p.translate(pivot.x(), pivot.y() - hop * 4.0)
                p.rotate(ang)
                p.translate(-pivot.x(), -pivot.y())
                p.drawPixmap(rect, hat, QRectF(hat.rect()))
                p.restore()

        f = QFont(theme.FONT_FAMILY)
        f.setWeight(QFont.Black)
        if self.state == "idle" and anim:
            for i in range(3):   # sleepy "z"s
                ph_ = (self._t * 0.35 + i / 3) % 1.0
                f.setPixelSize(int(12 + 10 * ph_))
                p.setFont(f)
                p.setPen(QColor(255, 210, 170, max(0, int(220 * (1 - ph_)))))
                p.drawText(QPointF(w * 0.80 + 18 * ph_, h * 0.30 - 46 * ph_), "z")
        elif self.state == "recording":
            on = not anim or int(self._t * 2) % 2 == 0     # without animations the dot just stays lit
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 107, 107, 230 if on else 90))
            p.drawEllipse(QPointF(w * 0.86, h * 0.12), 7, 7)

        for ang, life, s in (self._sparks if anim else ()):   # paw-print sparkles
            r = w * 0.30 + w * 0.22 * life
            pos = QPointF(c.x() + math.cos(ang) * r, c.y() * 0.95 + math.sin(ang) * r * 0.8)
            if disco > 0.3:
                pc = QColor.fromHsvF((ang / math.pi + self._t * 0.5) % 1.0, 0.55, 1.0)
            else:
                pc = QColor(theme.ORANGE_SOFT if self.state == "clicking" else theme.PURPLE)
            pc.setAlpha(max(0, min(255, int(230 * (1 - life)))))
            draw_paw(p, pos, s, pc)


class DiscoPanel(QFrame):
    """The left panel. Usually just the stylesheet background; during the disco, lights and music on top."""

    BEAMS = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.t = 0.0
        self.origin_y = 92        # where the disco ball shines from (above the cat)
        rnd = random.Random(5)
        self._stars = [(rnd.random(), rnd.random(), rnd.uniform(3, 8), rnd.random()) for _ in range(16)]
        self._notes = [(rnd.random(), rnd.uniform(0.6, 1.2), rnd.random(), rnd.random() < 0.4) for _ in range(7)]

    def set_level(self, level: float, t: float):
        changed = abs(level - self.level) > 1e-4 or level > 0
        self.level, self.t = level, t
        if changed:
            self.update()

    def paintEvent(self, _):
        lv = self.level
        if lv <= 0.001:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, t = self.width(), self.height(), self.t
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 23, 23)
        p.setClipPath(clip)
        p.setPen(Qt.NoPen)

        # dim the background so the light looks brighter
        p.fillRect(self.rect(), QColor(10, 4, 20, int(110 * lv)))

        ox, oy = w / 2, self.origin_y
        origin = QPointF(ox, oy)
        reach = math.hypot(w, h)
        for i in range(self.BEAMS):   # rotating beams
            ang = t * 0.9 + i * 2 * math.pi / self.BEAMS
            spread = 0.17 + 0.05 * math.sin(t * 2.1 + i)
            hue = (t * 0.12 + i / self.BEAMS) % 1.0
            col = QColor.fromHsvF(hue, 0.8, 1.0)
            g = QRadialGradient(origin, reach)
            c0 = QColor(col); c0.setAlpha(int(120 * lv))
            c1 = QColor(col); c1.setAlpha(int(45 * lv))
            c2 = QColor(col); c2.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(0.45, c1)
            g.setColorAt(1.0, c2)
            p.setBrush(g)
            p.drawPolygon(QPolygonF([origin,
                                     QPointF(ox + math.cos(ang - spread) * reach, oy + math.sin(ang - spread) * reach),
                                     QPointF(ox + math.cos(ang + spread) * reach, oy + math.sin(ang + spread) * reach)]))

        # pulsing "dance floor" spot at the bottom
        beat = abs(math.sin(t * BEAT_HZ * math.pi))
        fc = QColor.fromHsvF((t * 0.2 + 0.5) % 1.0, 0.7, 1.0)
        fg = QRadialGradient(QPointF(w / 2, h - 40), w * 0.75)
        fc.setAlpha(int((70 + 60 * beat) * lv))
        fg.setColorAt(0.0, fc)
        fc2 = QColor(fc); fc2.setAlpha(0)
        fg.setColorAt(1.0, fc2)
        p.setBrush(fg)
        p.drawEllipse(QPointF(w / 2, h - 40), w * 0.75, 120)

        # disco ball
        r = 13
        p.setPen(QColor(220, 220, 255, int(160 * lv)))
        p.drawLine(QPointF(ox, 0), QPointF(ox, oy - r))
        p.setPen(Qt.NoPen)
        bg = QRadialGradient(QPointF(ox - 4, oy - 4), r * 1.4)
        bg.setColorAt(0.0, QColor(255, 255, 255, int(255 * lv)))
        bg.setColorAt(1.0, QColor(150, 150, 190, int(255 * lv)))
        p.setBrush(bg)
        p.drawEllipse(origin, r, r)
        p.setPen(QColor(90, 90, 130, int(150 * lv)))
        for k in (-0.5, 0.0, 0.5):
            p.drawLine(QPointF(ox - r * math.sqrt(1 - k * k), oy + k * r), QPointF(ox + r * math.sqrt(1 - k * k), oy + k * r))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(origin, r * 0.45, r)
        p.setPen(Qt.NoPen)
        draw_sparkle(p, QPointF(ox + 9, oy - 9), 5 + 2 * beat, QColor(255, 255, 255, int(230 * lv)))

        # twinkling sparkles
        for x, y, s, ph in self._stars:
            tw = 0.5 + 0.5 * math.sin(t * 5 + ph * 6.28)
            col = QColor.fromHsvF((ph + t * 0.15) % 1.0, 0.35, 1.0, min(1.0, tw * lv))
            draw_sparkle(p, QPointF(12 + x * (w - 24), 60 + y * (h - 120)), s * (0.6 + 0.4 * tw), col)

        # notes floating around the cat
        for x, sp, ph, dbl in self._notes:
            u = (t * 0.28 * sp + ph) % 1.0
            nx = 26 + x * (w - 60) + 10 * math.sin(t * 2 + ph * 6)
            ny = 280 - u * 220
            col = QColor.fromHsvF((ph + t * 0.1) % 1.0, 0.45, 1.0, max(0.0, math.sin(u * math.pi)) * lv)
            draw_note(p, QPointF(nx, ny), 18, col, dbl)


class PromoToast(QFrame):
    """The cat's bubble with a link to the Telegram bot. Non-modal and never takes focus."""

    closed = Signal()

    def __init__(self, url: str, parent=None, show_ms: int = 15000):
        super().__init__(parent)
        self.setObjectName("promo")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._url = url
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 8, 10)
        lay.setSpacing(6)
        self.label = QLabel()
        self.label.setObjectName("promoText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.label.setFocusPolicy(Qt.NoFocus)
        self.label.setOpenExternalLinks(False)       # we open it ourselves, and only on click
        self.label.linkActivated.connect(self._open_link)
        lay.addWidget(self.label, 1)
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("promoClose")
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.dismiss)
        lay.addWidget(self.close_btn, 0, Qt.AlignTop)
        self._hide_timer = QTimer(self, singleShot=True, interval=show_ms)
        self._hide_timer.timeout.connect(self.dismiss)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._on_anim_done)
        self.opened_links = 0
        self.animated = True        # False: no fade-in (animations are off)
        self.hide()

    LINK_STYLE = "color:#ffb057; font-weight:900; text-decoration: underline;"

    def set_text(self, html: str):
        # dark theme: make the link orange instead of the default blue
        self.label.setText(html.replace("<a href=", f'<a style="{self.LINK_STYLE}" href='))

    def popup(self):
        self.show()
        self.raise_()
        self._anim.stop()
        self._hide_timer.start()
        if not self.animated:
            self._fx.setOpacity(1.0)
            return
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def dismiss(self):
        self._hide_timer.stop()
        if not self.isVisible():
            return
        self._anim.stop()
        if not self.animated:
            self._fx.setOpacity(0.0)
            self._on_anim_done()
            return
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_done(self):
        if self._fx.opacity() <= 0.01:
            self.hide()
            self.closed.emit()

    def _open_link(self, _href):
        # the only link in the app; the browser opens it only on click
        self.opened_links += 1
        QDesktopServices.openUrl(QUrl(self._url))
        self.dismiss()

    # while the cursor is over the bubble, do not hide it, so it can be read to the end
    def enterEvent(self, e):
        self._hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self.isVisible():
            self._hide_timer.start(4000)
        super().leaveEvent(e)
