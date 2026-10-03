import numpy as np
import time
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QPointF, QRectF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QImage, QPixmap, QColor, QFont, QPainter, QBrush, QPen, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QApplication
)
from ui.hud.design_system import *

# ── ROBOT CARD (SELECTION) ────────────────────────────────────────────
class RobotCard(QFrame):
    selected = Signal(str)

    def __init__(self, name, icon, desc, color_hex, parent=None):
        super().__init__(parent)
        self.name_str = name
        self.color_hex = color_hex
        self._hover_scale = 1.0
        self._hovered = False
        self._base_w = 260
        self._base_h = 370
        self.setFixedSize(self._base_w, self._base_h)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

        # Load appropriate card image
        if name == "PenLinux":
            self.card_pixmap = QPixmap("assets/textures/penlinux_card.png")
        elif name == "DinoByte":
            self.card_pixmap = QPixmap("assets/textures/dinobyte_card.png")
        else:
            self.card_pixmap = QPixmap() # Fallback

        # Shadow effect
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(18)
        self.shadow.setColor(QColor(0, 180, 255, 50))
        self.shadow.setOffset(0, 6)
        self.setGraphicsEffect(self.shadow)

        # Animation for hover
        self.scale_anim = QPropertyAnimation(self, b"hoverScale")
        self.scale_anim.setDuration(150)
        self.scale_anim.setEasingCurve(QEasingCurve.OutQuad)

    def get_hover_scale(self):
        return self._hover_scale

    def set_hover_scale(self, val):
        self._hover_scale = val
        self.update()

    hoverScale = Property(float, get_hover_scale, set_hover_scale)

    def scale_ui(self, scale):
        self._base_w = int(260 * scale)
        self._base_h = int(370 * scale)
        self.setFixedSize(self._base_w, self._base_h)

    def set_hovered(self, hovered: bool):
        if not self.isEnabled():
            hovered = False
        if self._hovered == hovered:
            return
        self._hovered = hovered
        
        self.scale_anim.stop()
        if hovered:
            self.scale_anim.setStartValue(self._hover_scale)
            self.scale_anim.setEndValue(1.05)
            self.shadow.setBlurRadius(30)
            self.shadow.setColor(QColor(self.color_hex))
        else:
            self.scale_anim.setStartValue(self._hover_scale)
            self.scale_anim.setEndValue(1.0)
            self.shadow.setBlurRadius(18)
            self.shadow.setColor(QColor(0, 180, 255, 50))
        self.scale_anim.start()

    def click(self):
        self.selected.emit(self.name_str)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click()

    def enterEvent(self, event):
        if not self.isEnabled():
            super().enterEvent(event)
            return
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.isEnabled():
            super().leaveEvent(event)
            return
        self.set_hovered(False)
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        if getattr(self, "card_pixmap", None) is None or self.card_pixmap.isNull():
            super().paintEvent(event)
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Calculate scaled dimensions
        w = int(self.width() * self._hover_scale)
        h = int(self.height() * self._hover_scale)
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        
        scaled_pixmap = self.card_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        px = x + (w - scaled_pixmap.width()) // 2
        py = y + (h - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(px, py, scaled_pixmap)
        super().paintEvent(event)
