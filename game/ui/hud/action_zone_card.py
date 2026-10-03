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

class ActionZoneCard(QFrame):
    """A single large action zone column — designed for CV gesture interaction.

    Each card covers 1/3 of the screen width and the entire height. Hovering
    anywhere in this column selects it, but visually there is a floating card
    in the center that slides up and glows on hover.
    """
    clicked = Signal()

    def __init__(self, icon_text, title, subtitle, accent_color, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self._base_title = title
        self._scale = 1.0
        self.setCursor(Qt.PointingHandCursor)

        # Visual floating card inside the column
        self.visual_card = QFrame(self)
        self.visual_card.setFixedSize(260, 340)
        
        # Internal layout of the visual card
        v_layout = QVBoxLayout(self.visual_card)
        v_layout.setContentsMargins(18, 28, 18, 20)
        v_layout.setSpacing(10)
        v_layout.setAlignment(Qt.AlignCenter)

        # Icon
        self.lbl_icon = QLabel(icon_text, self.visual_card)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet(f"font-size: 56px; color: {accent_color}; background: transparent; border: none;")
        v_layout.addWidget(self.lbl_icon)

        # Title
        self.lbl_title = QLabel(title, self.visual_card)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 18px;
            font-weight: 800;
            color: white;
            background: transparent;
            border: none;
            letter-spacing: 0.8px;
        """)
        v_layout.addWidget(self.lbl_title)

        # Subtitle (damage / description)
        self.lbl_sub = QLabel(subtitle, self.visual_card)
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: 14px;
            color: {accent_color};
            background: transparent;
            border: none;
        """)
        v_layout.addWidget(self.lbl_sub)
        v_layout.addStretch()

        # Instruction hint at bottom
        self.lbl_hint = QLabel("APONTE AQUI", self.visual_card)
        self.lbl_hint.setAlignment(Qt.AlignCenter)
        self.lbl_hint.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 11px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            letter-spacing: 1px;
        """)
        v_layout.addWidget(self.lbl_hint)

        # Transparent outer frame (so layout spaces the columns nicely)
        self.setStyleSheet("background: transparent; border: none;")

        self._default_y = 0
        self._current_anim = None

        self.scale_ui(1.0)

    def _apply_default_style(self):
        scale = getattr(self, "_scale", 1.0)
        border_radius = int(20 * scale)
        border_width = 2 * scale
        hint_font_size = int(11 * scale)
        hint_letter_spacing = scale
        self.visual_card.setStyleSheet(f"""
            background-color: {COLOR_CARD_BG};
            border: {border_width}px solid rgba(255, 255, 255, 0.12);
            border-radius: {border_radius}px;
        """)
        self.lbl_hint.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {hint_font_size}px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            letter-spacing: {hint_letter_spacing}px;
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_card()

    def _reposition_card(self):
        scale = getattr(self, "_scale", 1.0)
        w = self.width()
        h = self.height()
        cw = self.visual_card.width()
        ch = self.visual_card.height()
        x = (w - cw) // 2
        # Anchor to bottom with 30px margin to avoid overlap with webcam in top-left
        y = h - ch - int(30 * scale)
        self._default_y = y
        if not (self._current_anim and self._current_anim.state() == QPropertyAnimation.Running):
            self.visual_card.move(x, y)

    def slide_in_from_bottom(self):
        """Play a smooth slide up animation with an elastic bounce (OutBack)."""
        # Ensure latest layout positions are applied
        self._reposition_card()

        scale = getattr(self, "_scale", 1.0)
        w = self.width()
        cw = self.visual_card.width()
        x = (w - cw) // 2
        start_y = self._default_y + int(120 * scale) # start 120px below screen center

        self.visual_card.move(x, start_y)

        if self._current_anim:
            self._current_anim.stop()
        anim = QPropertyAnimation(self.visual_card, b"pos")
        anim.setDuration(600)
        anim.setStartValue(QPoint(x, start_y))
        anim.setEndValue(QPoint(x, self._default_y))
        anim.setEasingCurve(QEasingCurve.OutBack)
        self._current_anim = anim
        anim.start()

    def set_hovered(self, hovered):
        if not self.isEnabled():
            hovered = False
        if getattr(self, "_hovered", False) == hovered:
            return
        self._hovered = hovered

        scale = getattr(self, "_scale", 1.0)
        w = self.width()
        cw = self.visual_card.width()
        x = (w - cw) // 2

        if hovered:
            target_y = self._default_y - int(22 * scale) # slide up further when hovered

            border_radius = int(20 * scale)
            hover_border_width = 2.5 * scale
            hint_font_size = int(11 * scale)
            hint_letter_spacing = scale

            self.visual_card.setStyleSheet(f"""
                background-color: rgba(6, 14, 30, 0.96);
                border: {hover_border_width}px solid {self.accent_color};
                border-radius: {border_radius}px;
            """)
            self.lbl_hint.setStyleSheet(f"""
                font-family: {FONT_HUD};
                font-size: {hint_font_size}px;
                font-weight: 600;
                color: {self.accent_color};
                background: transparent;
                border: none;
                letter-spacing: {hint_letter_spacing}px;
            """)

            if self._current_anim:
                self._current_anim.stop()
            anim = QPropertyAnimation(self.visual_card, b"pos")
            anim.setDuration(250)
            anim.setStartValue(self.visual_card.pos())
            anim.setEndValue(QPoint(x, target_y))
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._current_anim = anim
            anim.start()
        else:
            self._apply_default_style()

            if self._current_anim:
                self._current_anim.stop()
            anim = QPropertyAnimation(self.visual_card, b"pos")
            anim.setDuration(200)
            anim.setStartValue(self.visual_card.pos())
            anim.setEndValue(QPoint(x, self._default_y))
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._current_anim = anim
            anim.start()

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

    def click(self):
        self.clicked.emit()

    def mousePressEvent(self, event):
        self.click()
        super().mousePressEvent(event)

    def set_enabled_state(self, enabled):
        self.setEnabled(enabled)
        scale = getattr(self, "_scale", 1.0)
        border_radius = int(20 * scale)
        icon_font_size = int(56 * scale)
        title_font_size = int(18 * scale)
        sub_font_size = int(14 * scale)
        hint_font_size = int(11 * scale)

        if not enabled:
            self.visual_card.setStyleSheet(f"""
                background-color: rgba(4, 6, 12, 0.65);
                border: {2 * scale}px solid rgba(40, 40, 50, 0.2);
                border-radius: {border_radius}px;
            """)
            self.lbl_icon.setStyleSheet(f"font-size: {icon_font_size}px; background: transparent; border: none; color: rgba(255,255,255,0.15);")
            self.lbl_title.setStyleSheet(f"font-family: {FONT_HUD}; font-size: {title_font_size}px; font-weight: 800; color: rgba(255,255,255,0.15); background: transparent; border: none;")
            self.lbl_sub.setStyleSheet(f"font-family: {FONT_MONO}; font-size: {sub_font_size}px; color: rgba(255,255,255,0.1); background: transparent; border: none;")
            self.lbl_hint.setStyleSheet(f"font-family: {FONT_HUD}; font-size: {hint_font_size}px; color: rgba(255,255,255,0.08); background: transparent; border: none;")
        else:
            self._apply_default_style()
            self.lbl_icon.setStyleSheet(f"font-size: {icon_font_size}px; background: transparent; border: none; color: {self.accent_color};")
            self.lbl_title.setStyleSheet(f"font-family: {FONT_HUD}; font-size: {title_font_size}px; font-weight: 800; color: white; background: transparent; border: none; letter-spacing: {0.8 * scale}px;")
            self.lbl_sub.setStyleSheet(f"font-family: {FONT_MONO}; font-size: {sub_font_size}px; color: {self.accent_color}; background: transparent; border: none;")

    def update_skill_info(self, icon, title, subtitle):
        self.lbl_icon.setText(icon)
        self.lbl_title.setText(title)
        self.lbl_sub.setText(subtitle)

    def scale_ui(self, scale):
        self._scale = scale
        w = int(260 * scale)
        h = int(340 * scale)
        self.visual_card.setFixedSize(w, h)
        
        # Scale margins & spacing
        self.visual_card.layout().setContentsMargins(int(18 * scale), int(28 * scale), int(18 * scale), int(20 * scale))
        self.visual_card.layout().setSpacing(int(10 * scale))
        
        # Icon
        icon_font_size = int(56 * scale)
        self.lbl_icon.setStyleSheet(f"font-size: {icon_font_size}px; color: {self.accent_color}; background: transparent; border: none;")
        
        # Title
        title_font_size = int(18 * scale)
        letter_spacing = 0.8 * scale
        self.lbl_title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {title_font_size}px;
            font-weight: 800;
            color: white;
            background: transparent;
            border: none;
            letter-spacing: {letter_spacing}px;
        """)
        
        # Subtitle
        sub_font_size = int(14 * scale)
        self.lbl_sub.setStyleSheet(f"""
            font-family: {FONT_MONO};
            font-size: {sub_font_size}px;
            color: {self.accent_color};
            background: transparent;
            border: none;
        """)
        
        # Hint
        hint_font_size = int(11 * scale)
        hint_letter_spacing = scale
        self.lbl_hint.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {hint_font_size}px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            letter-spacing: {hint_letter_spacing}px;
        """)
        
        # Stylesheet base
        border_radius = int(20 * scale)
        border_width = 2 * scale
        self._default_card_style = f"""
            background-color: {COLOR_CARD_BG};
            border: {border_width}px solid rgba(255, 255, 255, 0.12);
            border-radius: {border_radius}px;
        """
        
        hover_border_width = 2.5 * scale
        self._hover_card_style = f"""
            background-color: rgba(6, 14, 30, 0.96);
            border: {hover_border_width}px solid {self.accent_color};
            border-radius: {border_radius}px;
        """
        
        # Apply style based on state
        self.set_enabled_state(self.isEnabled())
        
        # Reposition card
        self._reposition_card()


