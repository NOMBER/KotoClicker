"""The "Trim sound" dialog: pick a piece of a custom sound, listen to it and save it as a WAV."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from .. import sound_trim
from ..i18n import tr
from ..typography import nbsp
from . import theme

MIN_PIECE = 0.05      # shorter than 50 ms is not really a sound


def _fmt(sec: float) -> str:
    return f"{sec:.2f}"


class WaveView(QWidget):
    """Sound picture: the selected piece is highlighted; the edges can be dragged with the mouse."""

    rangeChanged = Signal(float, float)

    def __init__(self, peaks, duration, max_seconds, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self.setMinimumWidth(420)
        self.setCursor(Qt.SizeHorCursor)
        self.peaks = peaks
        self.duration = max(0.001, duration)
        self.max_seconds = max_seconds
        self.start, self.end = 0.0, min(duration, max_seconds)
        self._drag = None

    def set_range(self, start, end):
        self.start, self.end = start, end
        self.update()

    def _x(self, sec):
        return 8 + (self.width() - 16) * sec / self.duration

    def _sec(self, x):
        return max(0.0, min(self.duration, (x - 8) / max(1, self.width() - 16) * self.duration))

    def mousePressEvent(self, e):
        sec = self._sec(e.position().x())
        self._drag = "start" if abs(sec - self.start) <= abs(sec - self.end) else "end"
        self._move_edge(sec)

    def mouseMoveEvent(self, e):
        if self._drag:
            self._move_edge(self._sec(e.position().x()))

    def mouseReleaseEvent(self, _):
        self._drag = None

    def _move_edge(self, sec):
        if self._drag == "start":
            self.start = min(sec, self.end - MIN_PIECE)
            self.start = max(0.0, self.start)
        else:
            self.end = max(sec, self.start + MIN_PIECE)
            self.end = min(self.duration, self.end)
        self.update()
        self.rangeChanged.emit(self.start, self.end)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
        p.fillPath(bg, QColor(theme.FIELD))
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawPath(bg)
        x0, x1 = self._x(self.start), self._x(self.end)
        p.fillRect(QRectF(x0, 4, x1 - x0, h - 8), QColor(255, 154, 60, 46))
        # the "this is the most the cat will play" boundary
        limit = self.start + self.max_seconds
        mid = h / 2
        n = len(self.peaks)
        if n:
            bw = (w - 16) / n
            for i, v in enumerate(self.peaks):
                cx = 8 + (i + 0.5) * bw
                sec = (i + 0.5) / n * self.duration
                inside = self.start <= sec <= self.end
                col = QColor(theme.ORANGE) if inside and sec <= limit else QColor(255, 255, 255, 70)
                if inside and sec > limit:
                    col = QColor(255, 154, 60, 90)
                p.setPen(QPen(col, max(1.0, bw * 0.6), Qt.SolidLine, Qt.RoundCap))
                hh = max(1.0, v * (h / 2 - 10))
                p.drawLine(QPointF(cx, mid - hh), QPointF(cx, mid + hh))
        if limit < self.end:
            p.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.DashLine))
            p.drawLine(QPointF(self._x(limit), 6), QPointF(self._x(limit), h - 6))
        for x in (x0, x1):                       # edge handles
            p.setPen(QPen(QColor(theme.ORANGE_SOFT), 2))
            p.drawLine(QPointF(x, 4), QPointF(x, h - 4))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.ORANGE_SOFT))
            p.drawEllipse(QPointF(x, 8), 4, 4)
            p.drawEllipse(QPointF(x, h - 8), 4, 4)


class TrimDialog(QDialog):
    """choice after closing: "save" = save the piece [start, end); "nocut" = use the file as is; None = cancel."""

    def __init__(self, path: str, pcm: sound_trim.Pcm, event_label: str, max_seconds: float,
                 volume: float = 0.7, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("trim_title"))
        self.setModal(True)
        self.setObjectName("trimDialog")
        self.pcm = pcm
        self.max_seconds = max_seconds
        self.volume = volume
        self.choice = None
        self._sink = None
        self._buffer = None
        dur = pcm.duration
        self.start, self.end = 0.0, min(dur, max_seconds)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)
        title = QLabel(tr("trim_title"))
        title.setObjectName("sectionTitle")
        lay.addWidget(title)
        name = QLabel(Path(path).name)
        name.setObjectName("cardTitle")
        name.setToolTip(str(path))
        name.setText(name.fontMetrics().elidedText(Path(path).name, Qt.ElideMiddle, 460))
        lay.addWidget(name)
        info = QLabel(nbsp(tr("trim_for", event=event_label) + " · " + tr("trim_total", secs=_fmt(dur))))
        info.setObjectName("cardHint")
        lay.addWidget(info)

        self.wave = WaveView(sound_trim.peaks(pcm, 140), dur, max_seconds)
        self.wave.rangeChanged.connect(self._from_wave)
        lay.addWidget(self.wave)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.spin_start = QDoubleSpinBox(decimals=2, singleStep=0.05, minimum=0.0, maximum=dur)
        self.spin_end = QDoubleSpinBox(decimals=2, singleStep=0.05, minimum=0.0, maximum=dur)
        for sb in (self.spin_start, self.spin_end):
            sb.setFixedWidth(96)
            sb.setKeyboardTracking(False)
        self.spin_start.setValue(self.start)
        self.spin_end.setValue(self.end)
        self.spin_start.valueChanged.connect(self._from_spins)
        self.spin_end.valueChanged.connect(self._from_spins)
        lbl_s = QLabel(tr("trim_start"))
        lbl_s.setObjectName("cardHint")
        lbl_e = QLabel(tr("trim_end"))
        lbl_e.setObjectName("cardHint")
        row.addWidget(lbl_s)
        row.addWidget(self.spin_start)
        row.addSpacing(8)
        row.addWidget(lbl_e)
        row.addWidget(self.spin_end)
        row.addSpacing(8)
        self.sel_label = QLabel()
        self.sel_label.setObjectName("cardTitle")
        row.addWidget(self.sel_label)
        row.addStretch(1)
        self.btn_play = QPushButton(tr("trim_play"))
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self._toggle_preview)
        row.addWidget(self.btn_play)
        lay.addLayout(row)

        self.max_label = QLabel(nbsp(tr("trim_max", max=f"{max_seconds:g}")))
        self.max_label.setObjectName("cardHint")
        self.max_label.setWordWrap(True)
        lay.addWidget(self.max_label)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch(1)
        self.btn_nocut = QPushButton(tr("trim_nocut"))
        self.btn_nocut.setToolTip(tr("trim_nocut_tip"))
        self.btn_nocut.clicked.connect(lambda: self._finish("nocut"))
        self.btn_cancel = QPushButton(tr("trim_cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton(tr("trim_save"))
        self.btn_save.setObjectName("accent")
        self.btn_save.setToolTip(tr("trim_save_tip"))
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(lambda: self._finish("save"))
        for b in (self.btn_nocut, self.btn_cancel, self.btn_save, self.btn_play):
            b.setCursor(Qt.PointingHandCursor)
        btns.addWidget(self.btn_nocut)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        lay.addLayout(btns)
        self._sync_label()

    # --- choosing the piece ---
    def set_range(self, start: float, end: float):
        dur = self.pcm.duration
        start = max(0.0, min(start, dur - MIN_PIECE))
        end = max(start + MIN_PIECE, min(end, dur))
        self.start, self.end = start, end
        for sb, v in ((self.spin_start, start), (self.spin_end, end)):
            sb.blockSignals(True)
            sb.setValue(v)
            sb.blockSignals(False)
        self.wave.set_range(start, end)
        self._sync_label()

    def _from_wave(self, start, end):
        self.set_range(start, end)

    def _from_spins(self, *_):
        self.set_range(self.spin_start.value(), self.spin_end.value())

    def _sync_label(self):
        self.sel_label.setText(tr("trim_sel", secs=_fmt(self.end - self.start)))

    def played_range(self):
        """What will actually sound: the selection, but not longer than the event maximum."""
        return self.start, min(self.end, self.start + self.max_seconds)

    # --- listen (straight from memory, no temporary files) ---
    def _toggle_preview(self):
        if self._sink is not None:
            self._stop_preview()
            return
        try:
            from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices
        except ImportError:
            return
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self.max_label.setText(nbsp(tr("msg_no_audio")))
            return
        a, b = self.played_range()
        piece = sound_trim.trim(self.pcm, a, b)
        fmt = QAudioFormat()
        fmt.setSampleRate(piece.rate)
        fmt.setChannelCount(piece.channels)
        fmt.setSampleFormat(QAudioFormat.Int16)
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(piece.to_bytes()))
        self._buffer.open(QIODevice.ReadOnly)
        self._sink = QAudioSink(device, fmt, self)
        self._sink.setVolume(max(0.0, min(1.0, self.volume)))
        self._sink.stateChanged.connect(lambda st: st == QAudio.IdleState and self._stop_preview())
        self._sink.start(self._buffer)
        self.btn_play.setText(tr("trim_stop"))

    def _stop_preview(self):
        sink, self._sink = self._sink, None
        if sink is not None:
            sink.stop()
            sink.deleteLater()
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        self.btn_play.setText(tr("trim_play"))

    @property
    def previewing(self) -> bool:
        return self._sink is not None

    def _finish(self, choice):
        self.choice = choice
        self.accept()

    def done(self, r):
        self._stop_preview()
        super().done(r)
