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
from ui.hud.webcam_widget import WebcamWidget

class PlayerHUDOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self._scale = 1.0
        self.setFixedSize(328, 340)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.setStyleSheet(f"""
            PlayerHUDOverlay {{
                background-color: {GLASS_DARK};
                border: none;
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Webcam feed
        self.webcam = WebcamWidget(self)
        layout.addWidget(self.webcam, 0, Qt.AlignCenter)

        # Stats container
        self.stats_container = QWidget(self)
        self.stats_container.setStyleSheet("background: transparent; border: none;")
        stats_layout = QVBoxLayout(self.stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)

        # Player name + HP value
        p_header = QHBoxLayout()
        self.lbl_p_name = QLabel("PLAYER", self.stats_container)
        self.lbl_p_name.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-weight: 700;
            font-size: 15px;
            color: {COLOR_CYAN};
            border: none;
            background: transparent;
            letter-spacing: 0.8px;
        """)
        self.lbl_p_hp_val = QLabel("100 / 100", self.stats_container)
        self.lbl_p_hp_val.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: 14px;
            font-weight: bold;
            color: white;
            border: none;
            background: transparent;
        """)
        p_header.addWidget(self.lbl_p_name)
        p_header.addStretch()
        p_header.addWidget(self.lbl_p_hp_val)
        stats_layout.addLayout(p_header)

        # HP bar — player themed
        self.p_hp_bar = QProgressBar(self.stats_container)
        self.p_hp_bar.setRange(0, 100)
        self.p_hp_bar.setValue(100)
        self.p_hp_bar.setTextVisible(False)
        self.p_hp_bar.setFixedHeight(10)
        self.p_hp_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #005a8c, stop:0.5 #0090ff, stop:1 {COLOR_CYAN});
                border-radius: 4px;
            }}
        """)
        stats_layout.addWidget(self.p_hp_bar)

        # Status effects
        self.lbl_p_status = QLabel("", self.stats_container)
        self.lbl_p_status.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 12px;
            color: {COLOR_YELLOW};
            font-weight: bold;
            border: none;
            background: transparent;
        """)
        stats_layout.addWidget(self.lbl_p_status)

        layout.addWidget(self.stats_container)
        
        # Minigame Color Overlays
        self.left_color_overlay = QFrame(self)
        self.left_color_overlay.hide()
        left_layout = QVBoxLayout(self.left_color_overlay)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_label = QLabel(self.left_color_overlay)
        self.left_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.left_label)
        
        self.right_color_overlay = QFrame(self)
        self.right_color_overlay.hide()
        right_layout = QVBoxLayout(self.right_color_overlay)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_label = QLabel(self.right_color_overlay)
        self.right_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.right_label)
        
        # Minigame Timer Bar
        self.minigame_timer_bar = QProgressBar(self)
        self.minigame_timer_bar.setRange(0, 100)
        self.minigame_timer_bar.setValue(100)
        self.minigame_timer_bar.setTextVisible(False)
        self.minigame_timer_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #cc9900, stop:1 {COLOR_YELLOW});
            }}
        """)
        self.minigame_timer_bar.hide()

        self._minigame_active = False
        self._minigame_intro_active = False
        self._minigame_attack_dir = "left"

        self.scale_ui(1.0)

    def scale_ui(self, scale):
        self._scale = scale
        w = int(328 * scale)
        if self.stats_container.isVisible():
            h = int(340 * scale)
        else:
            h = int(253 * scale)
        self.setFixedSize(w, h)
        
        self.layout().setContentsMargins(int(14 * scale), int(14 * scale), int(14 * scale), int(14 * scale))
        self.layout().setSpacing(int(10 * scale))
        
        border_radius = int(14 * scale)
        self.setStyleSheet(f"""
            PlayerHUDOverlay {{
                background-color: {GLASS_DARK};
                border: none;
                border-radius: {border_radius}px;
            }}
        """)
        
        self.webcam.scale_ui(scale)
        
        self.stats_container.layout().setSpacing(int(6 * scale))
        
        name_font_size = int(15 * scale)
        letter_spacing = 0.8 * scale
        self.lbl_p_name.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-weight: 700;
            font-size: {name_font_size}px;
            color: {COLOR_CYAN};
            border: none;
            background: transparent;
            letter-spacing: {letter_spacing}px;
        """)
        
        val_font_size = int(14 * scale)
        self.lbl_p_hp_val.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: {val_font_size}px;
            font-weight: bold;
            color: white;
            border: none;
            background: transparent;
        """)
        
        bar_h = int(10 * scale)
        self.p_hp_bar.setFixedHeight(bar_h)
        bar_radius = int(5 * scale)
        bar_chunk_radius = int(4 * scale)
        bar_border = 1.5 * scale
        self.p_hp_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: {bar_border}px solid rgba(255, 255, 255, 0.12);
                border-radius: {bar_radius}px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #005a8c, stop:0.5 #0090ff, stop:1 {COLOR_CYAN});
                border-radius: {bar_chunk_radius}px;
            }}
        """)
        
        status_font_size = int(12 * scale)
        self.lbl_p_status.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {status_font_size}px;
            color: {COLOR_YELLOW};
            font-weight: bold;
            border: none;
            background: transparent;
        """)

    def hide_stats(self):
        """Hides the stats and player life bar, and resizes overlay to wrap only the webcam."""
        self.stats_container.hide()
        scale = getattr(self, "_scale", 1.0)
        self.setFixedHeight(int(253 * scale)) # 225 webcam height + 28 margin

    def show_stats(self):
        """Shows the stats and player life bar, and restores original overlay size."""
        self.stats_container.show()
        scale = getattr(self, "_scale", 1.0)
        self.setFixedHeight(int(340 * scale)) # restore original height

    def update_minigame_overlays(self, hold_time=0.0):
        if not getattr(self, "_minigame_active", False) or getattr(self, "_minigame_intro_active", False):
            return
            
        attack_dir = getattr(self, "_minigame_attack_dir", "left")
        
        # Replace accumulation progress with a fixed instruction text
        safe_text = "SEGURO"
        
        # Only set the stylesheet ONCE when the minigame starts or if we need a static color
        if not getattr(self, "_dodge_styles_applied", False):
            font_style = f"font-family: '{FONT_HUD}'; font-weight: 900; font-size: {int(48 * self._scale)}px; letter-spacing: 2px; background: transparent;"
            
            danger_color = "rgba(220, 20, 20, 90)"  # Static translucent red
            safe_color = "rgba(0, 0, 0, 220)"       # Static dark background
            
            if attack_dir == "left":
                self.left_color_overlay.setStyleSheet(f"background-color: {danger_color}; border: none;")
                self.left_label.setText("PERIGO")
                self.left_label.setStyleSheet(font_style + "color: rgba(255, 80, 80, 220);")
                
                self.right_color_overlay.setStyleSheet(f"background-color: {safe_color}; border: none;")
                self.right_label.setStyleSheet(font_style + "color: rgba(180, 255, 180, 220);")
            else:
                self.left_color_overlay.setStyleSheet(f"background-color: {safe_color}; border: none;")
                self.left_label.setStyleSheet(font_style + "color: rgba(180, 255, 180, 220);")
                
                self.right_color_overlay.setStyleSheet(f"background-color: {danger_color}; border: none;")
                self.right_label.setText("PERIGO")
                self.right_label.setStyleSheet(font_style + "color: rgba(255, 80, 80, 220);")
                
            self._dodge_styles_applied = True
            
        # Update text only on the safe side, dynamically
        if attack_dir == "left":
            self.right_label.setText(safe_text)
        else:
            self.left_label.setText(safe_text)
            
        self.left_color_overlay.raise_()
        self.right_color_overlay.raise_()
        if hasattr(self, "minigame_timer_bar") and self.minigame_timer_bar.isVisible():
            self.minigame_timer_bar.raise_()


# ── ACTIONS HUD OVERLAY (BOTTOM CENTER - GESTURE ZONES) ───────────────
