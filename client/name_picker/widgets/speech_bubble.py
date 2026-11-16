# -*- coding: utf-8 -*-
"""依附于桌宠的无边框气泡。"""
from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication


class SpeechBubble(QWidget):
    """依附于桌宠的无边框气泡。"""

    def __init__(self, text, pet, duration=5):
        super().__init__(
            None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.pet = pet

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 24)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "color: #333333; font-size: 14px; font-weight: bold; background: transparent;"
        )
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        fm = self.label.fontMetrics()
        text_width = max(fm.boundingRect(text).width(), 80)
        self.setFixedWidth(min(text_width + 40, 260))

        self._duration = duration
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -14)
        path.addRoundedRect(rect, 10, 10)

        cx = self.width() / 2
        path.moveTo(cx - 8, rect.bottom())
        path.lineTo(cx, rect.bottom() + 10)
        path.lineTo(cx + 8, rect.bottom())

        painter.setPen(QPen(QColor("#4A90E2"), 2))
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawPath(path)

    def show_bubble(self):
        self.update_position()
        self.show()
        self.raise_()
        QTimer.singleShot(self._duration * 1000, self.close)

    def update_position(self):
        """更新气泡位置，使其跟随桌宠。"""
        pet_geo = self.pet.geometry()
        x = pet_geo.x() + (pet_geo.width() - self.width()) // 2
        y = pet_geo.y() - self.height() + 15

        screen = QApplication.primaryScreen().availableGeometry()
        if x < 0:
            x = 10
        if x + self.width() > screen.width():
            x = screen.width() - self.width() - 10
        if y < 0:
            y = 10

        self.move(x, y)