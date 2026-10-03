import numpy as np
import time
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QPointF, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QImage, QPixmap, QColor, QFont, QPainter, QBrush, QPen, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QApplication
)
from ui.hud.design_system import *

HAND_CONNECTIONS = [
    (0, 1), (0, 5), (0, 9), (0, 13), (0, 17),
    (1, 2), (2, 3), (3, 4),
    (5, 6), (6, 7), (7, 8),
    (9, 10), (10, 11), (11, 12),
    (13, 14), (14, 15), (15, 16),
    (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17)
]

class CVCursorWidget(QWidget):
    """GhostHand Overlay CVCursorWidget — Renders Sci-Fi neon bone graph landmarks & UI hover dwell ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self._scale = 1.0
        self.progress = 0.0
        self.closed = False
        self.target_x = None
        self.target_y = None
        self.hands_data = []

        # Window flags: Frameless translucent overlay
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        self._sync_geometry()
        self._active = False
        self.show()

    def _sync_geometry(self):
        if self.main_win and hasattr(self.main_win, "geometry"):
            self.setGeometry(self.main_win.geometry())

    def scale_ui(self, scale):
        self._scale = scale

    def set_cursor_state(self, x, y, progress, closed, hands_data=None):
        self.progress = progress
        self.closed = closed
        self.target_x = x
        self.target_y = y
        self.hands_data = hands_data or []

        if (x is None and y is None and not self.hands_data) or getattr(self, "_hide_for_minigame", False):
            self._active = False
        else:
            self._active = True
            self._sync_geometry()
            if not self.isVisible():
                self.show()

        self.update()

    def paintEvent(self, event):
        if not getattr(self, "_active", False):
            return
        painter = QPainter()
        if not painter.begin(self):
            return
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        scale = getattr(self, "_scale", 1.0)

        index_tip_pt = None

        if self.hands_data:
            glow_pen = QPen(QColor(0, 180, 255, 70), 6 * scale)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            inner_pen = QPen(QColor(0, 245, 255, 220), 2.2 * scale)
            inner_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            for hand in self.hands_data:
                landmarks = hand.get("landmarks", [])
                if not landmarks or len(landmarks) < 21:
                    continue

                pixel_pts = [QPointF(lm[0] * w, lm[1] * h) for lm in landmarks]
                if len(pixel_pts) > 8:
                    index_tip_pt = pixel_pts[8]

                # 1. Sci-Fi Bone Graph Skeleton Lines
                painter.setPen(glow_pen)
                for idx1, idx2 in HAND_CONNECTIONS:
                    if idx1 < len(pixel_pts) and idx2 < len(pixel_pts):
                        painter.drawLine(pixel_pts[idx1], pixel_pts[idx2])

                painter.setPen(inner_pen)
                for idx1, idx2 in HAND_CONNECTIONS:
                    if idx1 < len(pixel_pts) and idx2 < len(pixel_pts):
                        painter.drawLine(pixel_pts[idx1], pixel_pts[idx2])

                # 2. 21 Joint Halos & Core Dots
                halo_brush = QBrush(QColor(0, 236, 255, 160))
                core_brush = QBrush(QColor(255, 255, 255, 240))
                painter.setPen(Qt.NoPen)
                for pt in pixel_pts:
                    painter.setBrush(halo_brush)
                    painter.drawEllipse(pt, 4.5 * scale, 4.5 * scale)
                    painter.setBrush(core_brush)
                    painter.drawEllipse(pt, 2.2 * scale, 2.2 * scale)

        # 2. Fingertip Dwell Progress Arc (Only rendered if hovering over interactive UI element)
        if index_tip_pt is None and self.target_x is not None and self.target_y is not None:
            index_tip_pt = QPointF(self.target_x, self.target_y)

        if index_tip_pt is not None:
            center_x = index_tip_pt.x()
            center_y = index_tip_pt.y()
            radius = 20.0 * scale

            # If no hand landmarks are showing (mouse fallback), draw default cursor dot & ring
            if not self.hands_data:
                pen_bg = QPen(QColor(0, 236, 255, 45), 2.5 * scale)
                painter.setPen(pen_bg)
                painter.setBrush(Qt.NoBrush)
                rect = QRectF(center_x - radius, center_y - radius, radius * 2.0, radius * 2.0)
                painter.drawEllipse(rect)

                if self.progress > 0:
                    pen_active = QPen(QColor(0, 236, 255, 230), 4.0 * scale)
                    painter.setPen(pen_active)
                    span_angle = int(-(self.progress / 100.0) * 360 * 16)
                    painter.drawArc(rect, 90 * 16, span_angle)

                core_color = QColor(255, 34, 68) if self.closed else QColor(0, 236, 255)
                painter.setBrush(QBrush(core_color))
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5 * scale))
                dot_size = (14 if self.closed else 9) * scale
                painter.drawEllipse(QRectF(center_x - dot_size / 2.0, center_y - dot_size / 2.0, dot_size, dot_size))
            else:
                # When hand landmarks are showing, hide fingertip cursor dot & ring; draw ONLY dwell progress arc on hover
                if self.progress > 0:
                    pen_active = QPen(QColor(0, 236, 255, 230), 4.0 * scale)
                    painter.setPen(pen_active)
                    rect = QRectF(center_x - radius, center_y - radius, radius * 2.0, radius * 2.0)
                    span_angle = int(-(self.progress / 100.0) * 360 * 16)
                    painter.drawArc(rect, 90 * 16, span_angle)

        painter.end()


# ── MINIGAME FULLSCREEN INSTRUCTION OVERLAY ──────────────────────────
