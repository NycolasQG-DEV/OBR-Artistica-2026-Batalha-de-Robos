# ui/hud/attack_overlay.py — overlay de pintura e renderização do minigame de ataque
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import QFrame, QProgressBar
from ui.hud.design_system import COLOR_YELLOW

class AttackMinigameOverlay(QFrame):
    """Fullscreen overlay that renders attack minigame visuals using QPainter.

    This overlay sits on top of the webcam feed and draws the minigame elements
    (targets, energy bars, arrows) using the minigame's paint() method.
    It also shows the hand cursor position during the minigame.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._scale = 1.0
        self._minigame = None
        self._hand_pos = None  # (nx, ny) normalized

        # Timer bar at top
        self.timer_bar = QProgressBar(self)
        self.timer_bar.setRange(0, 100)
        self.timer_bar.setValue(100)
        self.timer_bar.setTextVisible(False)
        self.timer_bar.setFixedHeight(8)
        self.timer_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #cc9900, stop:1 {COLOR_YELLOW});
            }}
        """)

        # Repaint timer (~25 FPS paint — equilibra fluidez visual com uso de CPU)
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(40)
        self._paint_timer.timeout.connect(self.update_minigame_state)

    def update_minigame_state(self):
        """Update any Qt widget properties outside paintEvent."""
        if self._minigame and self._minigame._started and not self._minigame._finished:
            frac = self._minigame.get_time_fraction()
            self.timer_bar.setValue(int(frac * 100))
        self.update()

    def set_minigame(self, minigame):
        """Set the active minigame to render."""
        self._minigame = minigame

    def set_hand_pos(self, nx, ny):
        """Update hand position for rendering."""
        if nx is not None and ny is not None:
            self._hand_pos = (nx, ny)
        else:
            self._hand_pos = None

    def start_painting(self):
        """Start the repaint timer."""
        self._paint_timer.start()
        self.show()
        self.raise_()

    def stop_painting(self):
        """Stop the repaint timer."""
        self._paint_timer.stop()
        self.hide()

    def scale_ui(self, scale):
        self._scale = scale
        self.timer_bar.setFixedHeight(int(8 * scale))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.timer_bar.setGeometry(0, 0, self.width(), self.timer_bar.height())

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        scale = self._scale

        # Dark overlay background
        painter.fillRect(0, 0, w, h, QColor(4, 8, 16, 160))
        
        # Transparent scanlines overlay on background
        painter.fillRect(0, 0, w, h, QColor(4, 8, 16, 80))

        if self._minigame and self._minigame._started and not self._minigame._finished:
            # Render the minigame visuals
            self._minigame.paint(painter, w, h, scale)

            # Draw hand cursor if detected
            if self._hand_pos:
                if hasattr(self._minigame, "draw_custom_cursor"):
                    self._minigame.draw_custom_cursor(painter, self._hand_pos[0], self._hand_pos[1], w, h, scale)
                else:
                    hx = int(self._hand_pos[0] * w)
                    hy = int(self._hand_pos[1] * h)
                    cursor_r = int(16 * scale)

                    # Outer ring
                    painter.setPen(QPen(QColor(0, 236, 255, 160), 2.5 * scale))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(hx, hy), cursor_r + 4, cursor_r + 4)

                    # Inner dot
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor(0, 236, 255, 200)))
                    painter.drawEllipse(QPointF(hx, hy), cursor_r // 2, cursor_r // 2)

        elif self._minigame and self._minigame._finished:
            # Show result
            result = self._minigame.get_result()
            result_config = {
                "excellent": ("PERFEITO!", QColor(35, 255, 120)),
                "good": ("✓ BOM!", QColor(255, 200, 50)),
                "poor": ("✗ FRACO!", QColor(255, 50, 50)),
            }
            text, color = result_config.get(result, ("?", QColor(255, 255, 255)))

            font = QFont("Bahnschrift", int(48 * scale), QFont.Bold)
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(QRectF(0, h * 0.35, w, h * 0.3), Qt.AlignCenter, text)

        painter.end()
