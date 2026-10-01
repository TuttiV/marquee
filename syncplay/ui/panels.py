"""Small building blocks for the main window: the shared progress strip."""
import math
from syncplay.ui import theme
from syncplay.utils import formatTime
from syncplay.vendor.Qt import QtCore, QtGui, QtWidgets
from syncplay.vendor.Qt.QtCore import Qt


class ProgressStrip(QtWidgets.QWidget):
    """The room's shared playback position as a slim bar with elapsed and total time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._position, self._duration, self._paused, self._dark = 0.0, 0.0, True, True
        self.setFixedHeight(26)

    def setState(self, position, duration, paused, dark):
        self._position = max(0.0, float(position or 0))
        self._duration = max(0.0, float(duration or 0))
        self._paused, self._dark = bool(paused), dark
        self.update()

    def fraction(self):
        return min(1.0, self._position / self._duration) if self._duration > 0 else 0.0

    def paintEvent(self, event):
        t = theme.tokens(self._dark)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        font = QtGui.QFont(self.font())
        font.setPixelSize(11)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        left = formatTime(self._position) if self._duration else ""
        right = formatTime(self._duration) if self._duration else ""
        leftW, rightW = metrics.horizontalAdvance(left) + 14, metrics.horizontalAdvance(right) + 14
        track = QtCore.QRectF(leftW, self.height() / 2.0 - 2, max(10, self.width() - leftW - rightW), 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QColor(t["surface2"]))
        painter.drawRoundedRect(track, 2, 2)
        if self._duration > 0:
            filled = QtCore.QRectF(track.left(), track.top(), track.width() * self.fraction(), track.height())
            painter.setBrush(QtGui.QColor(t["muted"] if self._paused else t["accent"]))
            painter.drawRoundedRect(filled, 2, 2)
            painter.setBrush(QtGui.QColor(t["text"]))
            painter.drawEllipse(QtCore.QPointF(filled.right(), track.center().y()), 5, 5)
        painter.setPen(QtGui.QColor(t["muted"]))
        painter.drawText(QtCore.QRectF(0, 0, leftW, self.height()), Qt.AlignVCenter | Qt.AlignRight, left)
        painter.drawText(QtCore.QRectF(self.width() - rightW, 0, rightW, self.height()), Qt.AlignVCenter | Qt.AlignLeft, right)
        painter.end()


class ClickableLabel(QtWidgets.QLabel):
    """A label that does something when clicked (used for the sync note in the status bar)."""
    clicked = QtCore.Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _qcolor(value):
    """A QColor from a token: "#rrggbb" or the "rgba(r, g, b, a)" text some tokens use."""
    text = str(value).strip()
    if text.startswith("rgba"):
        r, g, b, a = [part.strip() for part in text[text.index("(") + 1:text.rindex(")")].split(",")]
        return QtGui.QColor(int(r), int(g), int(b), int(round(float(a) * 255)))
    return QtGui.QColor(text)


def _mix(a, b, t):
    return QtGui.QColor(*(int(round(x + (y - x) * t)) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()), (a.alpha(), b.alpha()))))


class ReadyButton(QtWidgets.QPushButton):
    """The Ready toggle. Changing state glides between "Not ready" (an outlined button with an empty ring) and "Ready"
    (a soft green button whose ring fills in and draws a tick), in about a fifth of a second, however the state was
    changed: by you, by the room, or by Always ready."""
    DURATION = 220

    def __init__(self, *args):
        super().__init__(*args)
        self._t = 1.0 if self.isChecked() else 0.0
        self._target = self._t
        self._shown = False
        self._keyboardFocus = False
        self.setStyleSheet("QPushButton { background: transparent; border: none; min-height: 34px; padding: 0 16px; }")  # It paints its own box
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(self.DURATION)
        self._animation.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self._animation.valueChanged.connect(self._step)

    def _step(self, value):
        self._t = float(value)
        self.update()

    def animating(self):
        return self._animation.state() == QtCore.QAbstractAnimation.Running

    def _follow(self):
        target = 1.0 if self.isChecked() else 0.0
        if target == self._target:
            return
        self._target = target
        self._animation.stop()
        if not self._shown or not self.isVisible():
            self._t = target  # Nothing on screen to animate (start-up, hidden window)
            return
        self._animation.setStartValue(self._t)
        self._animation.setEndValue(target)
        self._animation.start()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._keyboardFocus = event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._keyboardFocus = False
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        self._follow()
        self._shown = True
        tokens = theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))
        t = self._t
        ready, muted, border = _qcolor(tokens["ready"]), _qcolor(tokens["muted"]), _qcolor(tokens["border"])
        soft = _qcolor(tokens["readySoft"])
        hover = self.underMouse() and self.isEnabled() and not self.isDown()
        edge = _mix(border, ready, max(t, 0.45 if hover else 0.0))
        fill = _mix(QtGui.QColor(soft.red(), soft.green(), soft.blue(), 0), soft, t)
        if self.isDown():
            fill = _mix(fill, _qcolor(tokens["surface2"]), 0.6 * (1 - t))
        textColor = _mix(muted, ready, t if t > 0 else (0.5 if hover else 0.0))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QtGui.QPen(edge, 1.2))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 8, 8)
        if self.hasFocus() and self._keyboardFocus:  # A ring only when you tabbed here, never after a mouse click
            ring = _qcolor(tokens["accent"])
            ring.setAlpha(170)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(ring, 1.6))
            painter.drawRoundedRect(rect.adjusted(2.5, 2.5, -2.5, -2.5), 6, 6)

        font = QtGui.QFont(self.font())
        font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        text = self.text()
        iconSize, gap = 18, 8
        total = iconSize + gap + metrics.horizontalAdvance(text)
        left = rect.center().x() - total / 2.0
        cx, cy = left + iconSize / 2.0, rect.center().y()
        scale = 1.0 + 0.14 * math.sin(math.pi * t) if 0.0 < t < 1.0 else 1.0  # A small pop while it fills
        painter.save()
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        ring = _mix(muted, ready, t)
        painter.setPen(QtGui.QPen(ring, 1.8))
        painter.setBrush(_mix(QtGui.QColor(ready.red(), ready.green(), ready.blue(), 0), ready, t))
        painter.drawEllipse(QtCore.QPointF(0, 0), 7.2, 7.2)
        progress = max(0.0, min(1.0, (t - 0.3) / 0.7))
        if progress > 0:  # The tick draws itself from its start to its end
            points = [QtCore.QPointF(-3.6, 0.3), QtCore.QPointF(-1.0, 2.9), QtCore.QPointF(3.8, -2.6)]
            lengths = [((points[i + 1].x() - points[i].x()) ** 2 + (points[i + 1].y() - points[i].y()) ** 2) ** 0.5 for i in range(2)]
            remaining = progress * sum(lengths)
            path = QtGui.QPainterPath(points[0])
            for i in range(2):
                if remaining <= 0:
                    break
                part = min(1.0, remaining / lengths[i])
                path.lineTo(QtCore.QPointF(points[i].x() + (points[i + 1].x() - points[i].x()) * part,
                                           points[i].y() + (points[i + 1].y() - points[i].y()) * part))
                remaining -= lengths[i]
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor(tokens["readyText"]), 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.restore()
        painter.setPen(textColor)
        painter.drawText(QtCore.QRectF(left + iconSize + gap, rect.top(), metrics.horizontalAdvance(text) + 2, rect.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.end()


class EmojiPicker(QtWidgets.QFrame):
    """A small popup grid of emoji; clicking one reports it and closes the popup."""
    picked = QtCore.Signal(str)
    COLUMNS = 8

    def __init__(self, emojis, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("emojiPicker")
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(2)
        self.buttons = []
        for index, emoji in enumerate(emojis):
            button = QtWidgets.QToolButton()
            button.setText(emoji)
            button.setAutoRaise(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedSize(34, 34)
            button.setStyleSheet("QToolButton { font-size: 19px; border: none; border-radius: 6px; background: transparent; } QToolButton:hover { background: rgba(128,128,128,0.25); }")
            button.clicked.connect(lambda checked=False, e=emoji: self._choose(e))
            grid.addWidget(button, index // self.COLUMNS, index % self.COLUMNS)
            self.buttons.append(button)

    def _choose(self, emoji):
        self.picked.emit(emoji)
        self.close()
