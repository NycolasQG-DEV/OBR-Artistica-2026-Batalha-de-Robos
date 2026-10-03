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

class BossHPBarOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self._scale = 1.0
        self.setFixedSize(480, 100)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.setStyleSheet(f"""
            BossHPBarOverlay {{
                background-color: {GLASS_DARK};
                border: 1.5px solid {GLASS_BORDER_RED};
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        # Header row: boss name + skull icon | HP value
        b_header = QHBoxLayout()
        self.lbl_b_name = QLabel("☠  BOSS", self)
        self.lbl_b_name.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-weight: 700;
            font-size: 16px;
            color: {COLOR_RED};
            border: none;
            background: transparent;
            letter-spacing: 1px;
        """)
        self.lbl_b_hp_val = QLabel("100 / 100", self)
        self.lbl_b_hp_val.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: 15px;
            font-weight: bold;
            color: white;
            border: none;
            background: transparent;
        """)

        self.lbl_match_timer = QLabel("01:30", self)
        self.lbl_match_timer.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: 16px;
            font-weight: 900;
            color: {COLOR_YELLOW};
            border: none;
            background: transparent;
        """)
        self.lbl_match_timer.hide()  # Remove visualmente da tela

        b_header.addWidget(self.lbl_b_name)
        b_header.addStretch()
        # Timer (self.lbl_match_timer) removido da interface visual a pedido do usuário
        b_header.addStretch()
        b_header.addWidget(self.lbl_b_hp_val)
        layout.addLayout(b_header)

        # HP bar — thick and dramatic
        self.b_hp_bar = QProgressBar(self)
        self.b_hp_bar.setRange(0, 100)
        self.b_hp_bar.setValue(100)
        self.b_hp_bar.setTextVisible(False)
        self.b_hp_bar.setFixedHeight(14)
        self.b_hp_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 7px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8b0a14, stop:0.4 #cc1828, stop:1 {COLOR_RED});
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self.b_hp_bar)

        # Status effects row
        self.lbl_b_status = QLabel("", self)
        self.lbl_b_status.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 12px;
            color: {COLOR_YELLOW};
            font-weight: bold;
            border: none;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self.lbl_b_status)
        
        self.scale_ui(1.0)

    def scale_ui(self, scale):
        self._scale = scale
        w = int(480 * scale)
        h = int(100 * scale)
        self.setFixedSize(w, h)
        
        self.layout().setContentsMargins(int(18 * scale), int(12 * scale), int(18 * scale), int(12 * scale))
        self.layout().setSpacing(int(8 * scale))
        
        border_radius = int(14 * scale)
        border_width = 1.5 * scale
        self.setStyleSheet(f"""
            BossHPBarOverlay {{
                background-color: {GLASS_DARK};
                border: {border_width}px solid {GLASS_BORDER_RED};
                border-radius: {border_radius}px;
            }}
        """)
        
        name_font_size = int(16 * scale)
        letter_spacing = scale
        self.lbl_b_name.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-weight: 700;
            font-size: {name_font_size}px;
            color: {COLOR_RED};
            border: none;
            background: transparent;
            letter-spacing: {letter_spacing}px;
        """)
        
        val_font_size = int(15 * scale)
        self.lbl_b_hp_val.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: {val_font_size}px;
            font-weight: bold;
            color: white;
            border: none;
            background: transparent;
        """)

        timer_font_size = int(16 * scale)
        self.lbl_match_timer.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: {timer_font_size}px;
            font-weight: 900;
            color: {COLOR_YELLOW};
            border: none;
            background: transparent;
        """)
        
        bar_h = int(14 * scale)
        self.b_hp_bar.setFixedHeight(bar_h)
        bar_radius = int(7 * scale)
        bar_chunk_radius = int(6 * scale)
        bar_border = 1.5 * scale
        self.b_hp_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: {bar_border}px solid rgba(255, 255, 255, 0.12);
                border-radius: {bar_radius}px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8b0a14, stop:0.4 #cc1828, stop:1 {COLOR_RED});
                border-radius: {bar_chunk_radius}px;
            }}
        """)
        
        status_font_size = int(12 * scale)
        status_letter_spacing = 0.5 * scale
        self.lbl_b_status.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {status_font_size}px;
            color: {COLOR_YELLOW};
            font-weight: bold;
            border: none;
            background: transparent;
            letter-spacing: {status_letter_spacing}px;
        """)


# ── PLAYER HUD OVERLAY (BOTTOM LEFT) ──────────────────────────────────
