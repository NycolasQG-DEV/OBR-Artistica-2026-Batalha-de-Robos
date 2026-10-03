import os
import sys
import time
import math
import subprocess
import cv2
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QProgressBar,
    QPushButton, QGraphicsDropShadowEffect, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QPixmap, QImage, QCursor, QResizeEvent
)

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
from ui.hud.cv_cursor import CVCursorWidget
from ui.hud.webcam_widget import WebcamWidget

if _slide_engine_mod:
    sys.modules['engine'] = _slide_engine_mod

_HAS_CV_CURSOR = True
_HAS_CV_INPUT = True
_HAS_WEBCAM_WIDGET = True


from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve

class ChampionCardButton(QPushButton):
    """Futuristic Cyberpunk Character Selection Card Button for PySide6."""

    def __init__(self, name: str, code: str, role: str, color_hex: str, accent_hex: str, stats: dict, desc: str, parent=None):
        super().__init__(parent)
        self.char_name = name
        self.char_code = code
        self.color_hex = color_hex
        self.accent_hex = accent_hex

        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: transparent; border: none;")

        # Load appropriate card image
        if name == "PenLinux":
            self.card_pixmap = QPixmap(os.path.join(GAME_DIR, "assets", "textures", "penlinux_card.png"))
        elif name == "DinoByte":
            self.card_pixmap = QPixmap(os.path.join(GAME_DIR, "assets", "textures", "dinobyte_card.png"))
        else:
            self.card_pixmap = QPixmap()

        self._hover_scale = 1.0
        self._is_hovered = False

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(18)
        self.shadow.setColor(QColor(self.color_hex))
        self.shadow.setOffset(0, 6)
        self.setGraphicsEffect(self.shadow)

        self.scale_anim = QPropertyAnimation(self, b"hoverScale")
        self.scale_anim.setDuration(150)
        self.scale_anim.setEasingCurve(QEasingCurve.OutQuad)

    def get_hover_scale(self):
        return self._hover_scale

    def set_hover_scale(self, val):
        self._hover_scale = val
        self.update()

    hoverScale = Property(float, get_hover_scale, set_hover_scale)

    def set_hover_progress(self, pct: float):
        hover = (pct > 0)
        if hover and not self._is_hovered:
            self._is_hovered = True
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._hover_scale)
            self.scale_anim.setEndValue(1.05)
            self.shadow.setBlurRadius(30)
            self.scale_anim.start()
        elif not hover and self._is_hovered:
            self._is_hovered = False
            self.scale_anim.stop()
            self.scale_anim.setStartValue(self._hover_scale)
            self.scale_anim.setEndValue(1.0)
            self.shadow.setBlurRadius(18)
            self.scale_anim.start()
            
    def enterEvent(self, event):
        self.set_hover_progress(1.0)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.set_hover_progress(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self.card_pixmap.isNull():
            return super().paintEvent(event)
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        w = int(self.width() * self._hover_scale)
        h = int(self.height() * self._hover_scale)
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        
        scaled_pixmap = self.card_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        px = x + (w - scaled_pixmap.width()) // 2
        py = y + (h - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(px, py, scaled_pixmap)


class SelectionSlidePlayer(BaseSlidePlayer):
    """Full-Screen Responsive Champion Selection Slide with Background Threaded CV Hand Tracking."""

    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.cap = None
        self.cv_input = None
        self.cv_cursor = None
        self.webcam_widget = None
        self.selected_champion = None
        self.is_confirmed = False

        self.hover_times = {"DinoByte": 0.0, "PenLinux": 0.0}
        self.last_update_t = time.time()

        self.setMouseTracking(True)
        self.cursor_pos = QPoint(0, 0)

        # Full background
        self.setStyleSheet("background: transparent;")
        self.bg_pixmap = QPixmap(os.path.join(GAME_DIR, "assets", "textures", "background_choose.png"))

        # USE THE EXISTING ROOT LAYOUT from BaseSlidePlayer!
        self.layout.setContentsMargins(40, 25, 40, 25)
        self.layout.setSpacing(15)

        # Header Section
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(4)

        self.lbl_title_img = QLabel(self)
        self.lbl_title_img.setAlignment(Qt.AlignCenter)
        self.lbl_title_img.setStyleSheet("background: transparent; border: none;")
        self.title_pixmap = QPixmap(os.path.join(GAME_DIR, "assets", "textures", "title_choose.png"))
        self.lbl_title_img.setPixmap(self.title_pixmap.scaledToWidth(800, Qt.SmoothTransformation))
        header_vbox.addWidget(self.lbl_title_img)

        self.layout.addLayout(header_vbox)

        # Both champions use the same click and hand-hover selection flow.
        self.cards_hbox = QHBoxLayout()
        self.cards_hbox.setSpacing(28)
        self.cards_hbox.setAlignment(Qt.AlignCenter)

        self.btn_dinobyte = ChampionCardButton(
            name="DinoByte",
            code="DINOBYTE",
            role="POWER STRIKER",
            color_hex="#ff9900",
            accent_hex="#ff4400",
            stats={"VELOCIDADE": 70, "AGILIDADE": 75, "FORÇA": 95},
            desc="Mordida Jurássica, Sucção Jurássica e Meteor Stomp.",
            parent=self,
        )
        self.btn_dinobyte.clicked.connect(lambda: self._confirm_selection("DinoByte"))

        self.btn_penlinux = ChampionCardButton(
            name="PenLinux",
            code="PENLINUX",
            role="AGILE STRIKER",
            color_hex="#ff007f",
            accent_hex="#b000ff",
            stats={"VELOCIDADE": 95, "AGILIDADE": 90, "FORÇA": 70},
            desc="Robô Striker Ágil com Esquiva Tática e Ataque de Asa Laser. Máxima mobilidade e contra-ataques velozes.",
            parent=self
        )
        self.btn_penlinux.clicked.connect(lambda: self._confirm_selection("PenLinux"))

        self.cards_hbox.addStretch(1)
        self.cards_hbox.addWidget(self.btn_dinobyte, stretch=1)
        self.cards_hbox.addWidget(self.btn_penlinux, stretch=1)
        self.cards_hbox.addStretch(1)

        self.layout.addLayout(self.cards_hbox, stretch=1)

        # Bottom Bar: Webcam Preview Box Centered
        bottom_hbox = QHBoxLayout()
        bottom_hbox.setSpacing(20)
        bottom_hbox.addStretch(1)

        # Live Webcam Feed Preview Box Centered
        if _HAS_WEBCAM_WIDGET:
            try:
                self.webcam_widget = WebcamWidget(self)
                self.webcam_widget.scale_ui_custom(320, 240)
                bottom_hbox.addWidget(self.webcam_widget)
            except Exception as e:
                print(f"[SelectionPlayer] Erro criando WebcamWidget PIP: {e}")
                self.webcam_widget = None

        bottom_hbox.addStretch(1)

        self.layout.addLayout(bottom_hbox)

        # Frame Processing Timer (~60 FPS)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._process_frame)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.cursor_pos = event.pos()

    async def prepare(self):
        # Initialize CVCursorWidget overlay
        if _HAS_CV_CURSOR and self.cv_cursor is None:
            try:
                main_win = self.window() or self
                self.cv_cursor = CVCursorWidget(main_win)
                self.cv_cursor.show()
                self.cv_cursor.raise_()
            except Exception as e:
                print(f"[SelectionPlayer] Erro ao iniciar CVCursorWidget: {e}")

    async def play(self):
        self.hover_times = {"DinoByte": 0.0, "PenLinux": 0.0}
        self.is_confirmed = False
        self.last_update_t = time.time()

        # Initialize Camera & CVInput Background Thread on Play
        if _HAS_CV_INPUT and self.cv_input is None:
            try:
                cam_idx = detect_camera_index()
                print(f"[SelectionPlayer] Abrindo câmera no índice {cam_idx}...")
                self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                if self.cap and self.cap.isOpened():
                    self.cv_input = CVInput(self.cap)
                    print(f"[SelectionPlayer] CVInput background thread iniciado com sucesso!")
                else:
                    self.cap = None
                    self.cv_input = None
            except Exception as e:
                print(f"[SelectionPlayer] Erro na câmera/CVInput: {e}")
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
        if self.cv_cursor:
            self.cv_cursor.hide()

    def _process_frame(self):
        if self.is_confirmed:
            return

        now = time.time()
        dt = max(0.001, now - self.last_update_t)
        self.last_update_t = now

        hand_nx = None
        hand_ny = None
        hands_data = []
        hand_closed = False

        # Retrieve coordinates and live camera preview frame from background CVInput thread
        if self.cv_input and getattr(self.cv_input, "_enabled", False):
            # Update live webcam video PIP box
            if self.webcam_widget and getattr(self.cv_input, "preview_rgb_bytes", None):
                self.webcam_widget.update_frame(
                    self.cv_input.preview_rgb_bytes,
                    self.cv_input.preview_w,
                    self.cv_input.preview_h
                )

            if getattr(self.cv_input, "_currently_detected", False) or getattr(self.cv_input, "detected_hands", None):
                hand_nx = self.cv_input._nx
                hand_ny = self.cv_input._ny
                hands_data = getattr(self.cv_input, "detected_hands", [])
                hand_closed = getattr(self.cv_input, "_hand_closed", False)

        # Map to pixel screen coordinates
        if hand_nx is not None and hand_ny is not None:
            cx = int(hand_nx * self.width())
            cy = int(hand_ny * self.height())
        else:
            # Fallback to mouse cursor position inside window
            pos = self.mapFromGlobal(QCursor.pos()) if hasattr(QCursor, 'pos') else self.cursor_pos
            cx = max(0, min(self.width(), pos.x()))
            cy = max(0, min(self.height(), pos.y()))

        global_pos = self.mapToGlobal(QPoint(cx, cy))

        # Find target widget under cursor position
        target_widget = QApplication.widgetAt(global_pos)

        active_pct = 0.0
        for name, button in (("DinoByte", self.btn_dinobyte), ("PenLinux", self.btn_penlinux)):
            hover = button.geometry().contains(cx, cy) or bool(
                target_widget and (target_widget == button or button.isAncestorOf(target_widget))
            )
            if hover:
                self.hover_times[name] += dt
                active_pct = min(100.0, self.hover_times[name] / 3.0 * 100.0)
                button.set_hover_progress(active_pct)
                if self.hover_times[name] >= 3.0:
                    self._confirm_selection(name)
                    return
            else:
                self.hover_times[name] = 0.0
                button.set_hover_progress(0.0)

        # Update Sci-Fi CVCursorWidget overlay on screen
        if self.cv_cursor:
            self.cv_cursor.setGeometry(self.window().geometry() if self.window() else self.geometry())
            self.cv_cursor.set_cursor_state(global_pos.x(), global_pos.y(), active_pct, hand_closed, hands_data)

    def _trigger_confirmation_effect(self, code: str):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        if hasattr(self, "bg_pixmap") and not self.bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.bg_pixmap)
        super().paintEvent(event)

    def _confirm_selection(self, champion_name: str):
        if self.is_confirmed:
            return
        self.is_confirmed = True
        self.selected_champion = champion_name
        self.timer.stop()

        main_win = self.window()
        if main_win:
            main_win.selected_champion = champion_name
            if hasattr(main_win, "runner"):
                main_win.runner.selected_champion = champion_name

        # Stop camera thread
        if self.cv_input:
            self.cv_input._running = False
        if self.cap:
            self.cap.release()
            self.cap = None

        if self.cv_cursor:
            self.cv_cursor.hide()

        # Trigger advance to next slide (ATO1-pt2.mp4) after short 500ms feedback delay
        QTimer.singleShot(500, self._advance_to_next_slide)

    def _advance_to_next_slide(self):
        main_win = self.window()
        if main_win and hasattr(main_win, "runner"):
            main_win.runner.skip_next()

