import os
import sys
import time
import math
import cv2
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, QPointF, QByteArray, QUrl
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPixmap, QImage, QCursor
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

# Add game directory to sys.path
GAME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "game"))
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

# Temporarily clear SlideEngine/engine from sys.modules during game module imports
_slide_engine_mod = sys.modules.get('engine')
if _slide_engine_mod and not hasattr(_slide_engine_mod, 'platform'):
    del sys.modules['engine']

from engine.platform.camera_detection import detect_camera_index
from engine.input.cv_input import CVInput
from ui.hud.svg_icons import SVG_HAND_OPEN, SVG_CHECKMARK

if _slide_engine_mod:
    sys.modules['engine'] = _slide_engine_mod


class HandProgressCircleWidget(QWidget):
    """Minimalist Circular Loading Indicator with Hand Icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self.progress = 0.0  # 0.0 to 1.0
        self.is_holding = False
        self.is_confirmed = False

        # Clean SVG Renderers
        self._hand_renderer = QSvgRenderer(QByteArray(SVG_HAND_OPEN.encode('utf-8')))
        self._check_renderer = QSvgRenderer(QByteArray(SVG_CHECKMARK.encode('utf-8')))

    def set_progress(self, val: float, holding: bool):
        self.progress = max(0.0, min(1.0, val))
        self.is_holding = holding
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        radius = min(cx, cy) - 10

        # ── 1. Fundo Circular Minimalista Translúcido ──
        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── 2. Trilha Estática do Anel (Linha fina discreta) ──
        track_pen = QPen(QColor(255, 255, 255, 40), 4)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.NoBrush)
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.drawEllipse(rect)

        # ── 3. Anel de Progresso Ativo (Arco Minimalista) ──
        if self.progress > 0.001:
            active_color = QColor(50, 255, 130) if self.is_confirmed else QColor(255, 255, 255)
            progress_pen = QPen(active_color, 5)
            progress_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(progress_pen)

            start_angle = 90 * 16
            span_angle = -int(self.progress * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # ── 4. Ícone Central da Mão ──
        icon_size = 76
        icon_rect = QRectF(cx - icon_size / 2, cy - icon_size / 2, icon_size, icon_size)

        if self.is_confirmed:
            self._check_renderer.render(painter, icon_rect)
        else:
            self._hand_renderer.render(painter, icon_rect)


class HandCalibrationSlidePlayer(BaseSlidePlayer):
    """
    Slide 1: Calibração Minimalista com Mão Aberta.
    - Câmera em fullscreen no fundo.
    - Interface limpa e minimalista sem janelas ou bordas brilhantes.
    """

    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.cap = None
        self.cv_input = None
        self.is_confirmed = False
        self.hold_time = 0.0
        self.TARGET_HOLD = 2.0  # 2.0s
        self.last_update_t = time.time()
        self.latest_pixmap = None

        self.audio_player = None
        self.audio_output = None

        self.setStyleSheet("background-color: #000000;")

        # Layout Minimalista Centralizado Direto na Tela
        self.layout.setContentsMargins(40, 60, 40, 60)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignCenter)

        # Spacer superior
        self.layout.addStretch(1)

        # Título Minimalista
        self.lbl_title = QLabel("Estenda a mão aberta por 2s", self)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 26px;
            font-weight: 600;
            color: #ffffff;
            background: transparent;
        """)
        self.layout.addWidget(self.lbl_title, 0, Qt.AlignCenter)

        # Widget do Anel de Progresso com Ícone da Mão
        self.progress_circle = HandProgressCircleWidget(self)
        self.layout.addWidget(self.progress_circle, 0, Qt.AlignCenter)

        # Subtítulo / Status
        self.lbl_status = QLabel("Posicione sua mão aberta em frente à câmera", self)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 15px;
            color: #cbd5e1;
            background: transparent;
        """)
        self.layout.addWidget(self.lbl_status, 0, Qt.AlignCenter)

        # Botão Minimalista para Pular / Avançar
        self.btn_skip = QPushButton("Pular", self)
        self.btn_skip.setCursor(Qt.PointingHandCursor)
        self.btn_skip.setFixedHeight(34)
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 17px;
                padding: 0 22px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.18);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
        """)
        self.btn_skip.clicked.connect(self._manual_confirm)
        self.layout.addWidget(self.btn_skip, 0, Qt.AlignCenter)

        # Spacer inferior
        self.layout.addStretch(1)

        # Timer ~60 FPS
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._process_frame)

    async def prepare(self):
        try:
            self.audio_player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(1.0)
        except Exception as e:
            print(f"[HandCalibrationSlidePlayer] Erro áudio: {e}")

    async def play(self):
        self.is_confirmed = False
        self.hold_time = 0.0
        self.last_update_t = time.time()

        if self.cv_input is None:
            try:
                cam_idx = detect_camera_index()
                self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                if self.cap and self.cap.isOpened():
                    self.cv_input = CVInput(self.cap)
                else:
                    self.cap = None
                    self.cv_input = None
            except Exception as e:
                print(f"[HandCalibrationSlidePlayer] Erro câmera/CV: {e}")
                self.cap = None
                self.cv_input = None

        self.timer.start()

    async def stop(self):
        self.timer.stop()
        if self.cv_input:
            self.cv_input._running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def _process_frame(self):
        if self.is_confirmed:
            return

        now = time.time()
        dt = max(0.001, now - self.last_update_t)
        self.last_update_t = now

        hand_detected = False
        hand_is_open = False

        if self.cv_input and getattr(self.cv_input, "_enabled", False):
            rgb_bytes = getattr(self.cv_input, "preview_rgb_bytes", None)
            w_f = getattr(self.cv_input, "preview_w", 640)
            h_f = getattr(self.cv_input, "preview_h", 480)

            if rgb_bytes:
                qimg = QImage(rgb_bytes, w_f, h_f, QImage.Format_RGB888)
                self.latest_pixmap = QPixmap.fromImage(qimg)
                self.update()

            detected_hands = getattr(self.cv_input, "detected_hands", [])
            if detected_hands:
                hand_detected = True
                for h in detected_hands:
                    if not h.get("closed", False):
                        hand_is_open = True
                        break

        if hand_is_open:
            self.hold_time += dt
            self.progress_circle.set_progress(self.hold_time / self.TARGET_HOLD, holding=True)

            rem = max(0.0, self.TARGET_HOLD - self.hold_time)
            pct = int(min(100.0, (self.hold_time / self.TARGET_HOLD) * 100.0))
            self.lbl_status.setText(f"Mão detectada — segure por mais {rem:.1f}s ({pct}%)")
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #4ade80; background: transparent;")

            if self.hold_time >= self.TARGET_HOLD:
                self._confirm_calibration()
        else:
            self.hold_time = max(0.0, self.hold_time - dt * 1.5)
            self.progress_circle.set_progress(self.hold_time / self.TARGET_HOLD, holding=False)

            if hand_detected:
                self.lbl_status.setText("Abra a palma da mão")
                self.lbl_status.setStyleSheet("font-size: 15px; color: #fbbf24; background: transparent;")
            else:
                self.lbl_status.setText("Posicione sua mão aberta em frente à câmera")
                self.lbl_status.setStyleSheet("font-size: 15px; color: #cbd5e1; background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # ── Feed da câmera em tela cheia com escurecimento suave ──
        if self.latest_pixmap and not self.latest_pixmap.isNull():
            scaled_bg = self.latest_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bx = (self.width() - scaled_bg.width()) // 2
            by = (self.height() - scaled_bg.height()) // 2
            painter.drawPixmap(bx, by, scaled_bg)

            # Película escura suave para garantir legibilidade limpa
            painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        else:
            painter.fillRect(self.rect(), QColor(10, 10, 10, 255))

        super().paintEvent(event)

    def _play_sfx(self, sound_name: str = "select.wav"):
        sfx_path = os.path.abspath(os.path.join(GAME_DIR, "assets", "sounds", sound_name))
        if not os.path.exists(sfx_path):
            sfx_path = os.path.abspath(os.path.join(GAME_DIR, "assets", "sounds", "whoosh.wav"))

        if os.path.exists(sfx_path) and self.audio_player:
            self.audio_player.setSource(QUrl.fromLocalFile(sfx_path))
            self.audio_player.play()

    def _manual_confirm(self):
        if not self.is_confirmed:
            self._confirm_calibration()

    def _confirm_calibration(self):
        self.is_confirmed = True
        self.timer.stop()
        self.progress_circle.is_confirmed = True
        self.progress_circle.set_progress(1.0, holding=False)

        self.lbl_title.setText("Concluído")
        self.lbl_title.setStyleSheet("font-size: 26px; font-weight: 600; color: #4ade80; background: transparent;")
        self.lbl_status.setText("Iniciando apresentação...")
        self.lbl_status.setStyleSheet("font-size: 15px; color: #4ade80; background: transparent;")

        self._play_sfx("select.wav")

        if self.cv_input:
            self.cv_input._running = False
        if self.cap:
            self.cap.release()
            self.cap = None

        QTimer.singleShot(400, self._advance_to_next_slide)

    def _advance_to_next_slide(self):
        main_win = self.window()
        if main_win and hasattr(main_win, "runner"):
            main_win.runner.skip_next()
