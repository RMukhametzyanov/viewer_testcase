"""Custom toggle switch widget."""

from PyQt5.QtCore import Qt, QRectF, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QCheckBox


class ToggleSwitch(QCheckBox):
    """Минимальный переключатель в стиле on/off."""

    def __init__(
        self,
        parent=None,
        *,
        bar_color: QColor | None = None,
        checked_color: QColor | None = None,
        handle_color: QColor | None = None,
    ):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setTristate(False)
        self._bar_color = bar_color or QColor("#3a3d46")
        self._checked_color = checked_color or QColor("#3ec6e0")
        self._handle_color = handle_color or QColor("#f5f6fa")
        self._handle_border = QColor(0, 0, 0, 40)
        self.setMinimumSize(52, 28)
        self.toggled.connect(self.update)

    def sizeHint(self):
        return QSize(52, 28)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(event.rect(), Qt.transparent)

        bar_rect = QRectF(4, self.height() / 2 - 10, self.width() - 8, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._checked_color if self.isChecked() else self._bar_color))
        painter.drawRoundedRect(bar_rect, 10, 10)

        handle_diameter = 16
        if self.isChecked():
            handle_x = bar_rect.right() - handle_diameter - 2
        else:
            handle_x = bar_rect.left() + 2
        handle_rect = QRectF(
            handle_x,
            bar_rect.center().y() - handle_diameter / 2,
            handle_diameter,
            handle_diameter,
        )

        painter.setBrush(QBrush(self._handle_color))
        painter.setPen(QPen(self._handle_border, 1))
        painter.drawEllipse(handle_rect)

