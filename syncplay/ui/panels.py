"""Small building blocks for the main window: the shared progress strip."""
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
