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

class WebcamWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self.setFixedSize(300, 225)
        self.setStyleSheet(f"""
            WebcamWidget {{
                background-color: #020408;
                border-radius: 15px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_video = QLabel(self)
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setScaledContents(True)
        self.lbl_video.setFixedSize(300, 225)
        layout.addWidget(self.lbl_video)

        # Static text overlaid
        self.lbl_status = QLabel("SEM SINAL DE VÍDEO\nUSE O MOUSE", self.lbl_video)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setGeometry(0, 0, 300, 225)
        self.lbl_status.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: 11px;
            font-weight: bold;
            color: {COLOR_RED};
            background-color: transparent;
        """)

        # CRT noise animation loop
        self._noise_timer = QTimer(self)
        self._noise_timer.setInterval(45)
        self._noise_timer.timeout.connect(self._animate_noise)
        self._noise_timer.start()

        self._has_video = False
        
        # Performance/signal recovery variables
        self._last_update = 0.0
        self._fallback_pix = None
        self._fallback_counter = 0
        self._fallback_max = 10  # frames to hold last good image when signal lost

    def scale_ui_custom(self, w, h):
        self.setFixedSize(w, h)
        self.lbl_video.setFixedSize(w, h)
        self.lbl_status.setGeometry(0, 0, w, h)

    def scale_ui(self, scale):
        self._scale = scale
        w = int(300 * scale)
        h = int(225 * scale)
        self.setFixedSize(w, h)
        self.lbl_video.setFixedSize(w, h)
        self.lbl_status.setGeometry(0, 0, w, h)
        
        status_font_size = int(11 * scale)
        self.lbl_status.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: {status_font_size}px;
            font-weight: bold;
            color: {COLOR_RED};
            background-color: transparent;
        """)
        
        border_radius = int(14 * scale)
        self.setStyleSheet(f"""
            WebcamWidget {{
                background-color: #020408;
                border: none;
                border-radius: {border_radius}px;
            }}
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from PySide6.QtGui import QPainterPath, QRegion
        from PySide6.QtCore import QRectF
        
        w = self.width()
        h = self.height()
        
        # Check if we are in fullscreen minigame mode (no rounded mask needed)
        is_fullscreen = False
        parent_overlay = self.parent()
        if parent_overlay:
            if getattr(parent_overlay, "_minigame_active", False) or getattr(parent_overlay, "_jurassic_bite_active", False):
                is_fullscreen = True
            
        if is_fullscreen:
            self.clearMask()
        else:
            border_radius = int(14 * getattr(self, "_scale", 1.0))
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, w, h), border_radius, border_radius)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def update_frame(self, rgb_bytes, w, h):
        import time
        now = time.time()
        pass
        if rgb_bytes is not None:
            self._has_video = True
            self.lbl_status.hide()
            self._noise_timer.stop()
            qimg = QImage(rgb_bytes, w, h, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.lbl_video.setPixmap(pix)
            self._fallback_pix = pix
            self._fallback_counter = self._fallback_max
            # Pre-cache low-res fullscreen optimized pixmap for minigame backgrounds
            self._cached_minigame_pix = pix.scaled(480, 270, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)
        else:
            # No new frame; keep last good frame for a few cycles
            if self._fallback_pix and self._fallback_counter > 0:
                self.lbl_video.setPixmap(self._fallback_pix)
                self._fallback_counter -= 1
                self._cached_minigame_pix = self._fallback_pix.scaled(480, 270, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)
            else:
                if self._has_video or not self._noise_timer.isActive():
                    self._has_video = False
                    self.lbl_status.show()
                    self._noise_timer.start()

    def _animate_noise(self):
        w_f, h_f = 120, 90
        noise = np.random.randint(15, 45, (h_f, w_f, 3), dtype=np.uint8)

        # Scanlines effect
        for y in range(0, h_f, 2):
            noise[y, :, :] = (noise[y, :, :] * 0.55).astype(np.uint8)

        qimg = QImage(noise.tobytes(), w_f, h_f, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_video.setPixmap(pix)
        self._cached_minigame_pix = pix.scaled(480, 270, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)


# ── BOSS HP BAR OVERLAY (TOP CENTER) ──────────────────────────────────
