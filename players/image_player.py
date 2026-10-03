import os
from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QLinearGradient, QFont, QResizeEvent
from PySide6.QtCore import Qt, QRectF
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

class ImageSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.lbl_image = QLabel(self)
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.lbl_image)

        self.raw_pixmap: QPixmap = None

    async def prepare(self):
        src = self.config.get("src")
        if src and os.path.exists(src):
            self.raw_pixmap = QPixmap(src)
        else:
            # Generate synthetic fallback image if asset doesn't exist
            self.raw_pixmap = self._generate_fallback_pixmap()

        self._update_scaled_pixmap()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self.raw_pixmap and not self.raw_pixmap.isNull():
            w = max(100, self.lbl_image.width())
            h = max(100, self.lbl_image.height())
            scaled = self.raw_pixmap.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)

    def _generate_fallback_pixmap(self) -> QPixmap:
        img = QImage(1920, 1080, QImage.Format_ARGB32)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, 1920, 1080)
        grad.setColorAt(0.0, QColor(20, 30, 48))
        grad.setColorAt(1.0, QColor(36, 59, 85))
        painter.fillRect(0, 0, 1920, 1080, grad)

        painter.setPen(QColor(0, 240, 255, 180))
        painter.drawRect(40, 40, 1840, 1000)

        font = QFont("Segoe UI", 42, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(0, 400, 1920, 100), Qt.AlignCenter, "DEMO IMAGE SLIDE")

        font.setPixelSize(24)
        painter.setFont(font)
        painter.setPen(QColor(0, 240, 255))
        painter.drawText(QRectF(0, 520, 1920, 50), Qt.AlignCenter, "Slide Engine — High Performance Async Renderer")
        painter.end()

        return QPixmap.fromImage(img)

