# ui/hud/robotic_vision_overlay.py — overlay de efeito visual de visão robótica CRT
import math
import random
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QRadialGradient, QPixmap, QImage
from PySide6.QtWidgets import QWidget
from ui.hud.design_system import FONT_MONO

class RoboticVisionOverlay(QWidget):
    """Overlay fullscreen que simula uma tela CRT antiga / visão robótica de ficção científica (Otimizado)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._scale = 1.0
        self._glitch_y = 0.0
        self._flicker_timer = 0.0
        self._rec_visible = True
        
        # Caches de renderização para alta performance
        self._cached_bg_vignette = None
        self._noise_pixmaps = []
        self._noise_frame_index = 0
        self._last_width = 0
        self._last_height = 0
        
        # Pré-inicializa os pixmaps de ruído/estática
        self._precompute_noise_patterns()
        
        # QTimer para atualizar efeitos animados a 60 FPS
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._on_tick)

    def start_effect(self):
        self._flicker_timer = 0.0
        self._timer.start()
        self.show()
        self.raise_()

    def stop_effect(self):
        self._timer.stop()
        self.hide()

    def scale_ui(self, scale):
        self._scale = scale

    def _on_tick(self):
        self._flicker_timer += 0.016
        self._glitch_y = (self._glitch_y + 160 * 0.016)
        self._noise_frame_index = (self._noise_frame_index + 1) % 4
        
        if int(self._flicker_timer * 2.2) % 2 == 0:
            self._rec_visible = True
        else:
            self._rec_visible = False
            
        self.update()

    def _precompute_noise_patterns(self):
        """Gera 4 pequenos pixmaps de ruído estático aleatório para ciclar em cache."""
        sz = 160
        for _ in range(4):
            img = QImage(sz, sz, QImage.Format_ARGB32)
            img.fill(QColor(0, 0, 0, 0))
            
            for x in range(sz):
                for y in range(sz):
                    if random.random() < 0.28:
                        val = random.randint(180, 255)
                        alpha = random.randint(15, 45)
                        img.setPixelColor(x, y, QColor(val, val // 2, 0, alpha))
            
            self._noise_pixmaps.append(QPixmap.fromImage(img))

    def _rebuild_static_cache(self, w, h):
        """Prepara uma textura contendo o gradiente e as scanlines fixas para evitar redesenho por frame."""
        self._cached_bg_vignette = QPixmap(w, h)
        self._cached_bg_vignette.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(self._cached_bg_vignette)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Color Tint (Laranja âmbar translúcido)
        tint = QColor(255, 110, 0, 14)
        painter.fillRect(0, 0, w, h, tint)

        # 2. CRT Scanlines
        scan_gap = int(max(3.0, 4.0 * self._scale))
        pen_scan = QPen(QColor(0, 0, 0, 32), 1)
        painter.setPen(pen_scan)
        for y in range(0, h, scan_gap):
            painter.drawLine(0, y, w, y)

        # 3. Vignette CRT
        radial = QRadialGradient(w / 2.0, h / 2.0, math.sqrt((w/2)**2 + (h/2)**2))
        radial.setColorAt(0.0, QColor(0, 0, 0, 0))
        radial.setColorAt(0.70, QColor(0, 0, 0, 10))
        radial.setColorAt(0.95, QColor(0, 0, 0, 110))
        radial.setColorAt(1.0, QColor(0, 0, 0, 190))
        painter.fillRect(0, 0, w, h, QBrush(radial))
        
        painter.end()
        
        self._last_width = w
        self._last_height = h

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        scale = self._scale
        
        # Cybernetic borders
        pad = int(40 * scale)
        pen_frame = QPen(QColor(255, 110, 0, 50), 1)
        painter.setPen(pen_frame)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(pad, pad, w - 2*pad, h - 2*pad)

        # Central target box
        center_x = w / 2.0
        center_y = h / 2.0
        pen_hud = QPen(QColor(255, 110, 0, 150), 1 * scale)
        painter.setPen(pen_hud)
        rect_sz = int(64 * scale)
        painter.drawRect(QRectF(center_x - rect_sz/2, center_y - rect_sz/2, rect_sz, rect_sz))

        # Crosshairs
        gap = int(10 * scale)
        hair_len = int(24 * scale)
        painter.drawLine(center_x, center_y - rect_sz/2 - gap, center_x, center_y - rect_sz/2 - gap - hair_len) # Top
        painter.drawLine(center_x, center_y + rect_sz/2 + gap, center_x, center_y + rect_sz/2 + gap + hair_len) # Bottom
        painter.drawLine(center_x - rect_sz/2 - gap, center_y, center_x - rect_sz/2 - gap - hair_len, center_y) # Left
        painter.drawLine(center_x + rect_sz/2 + gap, center_y, center_x + rect_sz/2 + gap + hair_len, center_y) # Right

        # Corner brackets
        pen_bracket = QPen(QColor(255, 110, 0, 220), 2.5 * scale)
        painter.setPen(pen_bracket)
        bracket_len = int(24 * scale)
        # Top-Left
        painter.drawLine(pad, pad, pad + bracket_len, pad)
        painter.drawLine(pad, pad, pad, pad + bracket_len)
        # Top-Right
        painter.drawLine(w - pad, pad, w - pad - bracket_len, pad)
        painter.drawLine(w - pad, pad, w - pad, pad + bracket_len)
        # Bottom-Left
        painter.drawLine(pad, h - pad, pad + bracket_len, h - pad)
        painter.drawLine(pad, h - pad, pad, h - pad - bracket_len)
        # Bottom-Right
        painter.drawLine(w - pad, h - pad, w - pad - bracket_len, h - pad)
        painter.drawLine(w - pad, h - pad, w - pad, h - pad - bracket_len)

        # Monospace Diagnostics
        font_hud = QFont(FONT_MONO, int(11 * scale))
        painter.setFont(font_hud)

        # Blinking REC
        rec_text = "● REC" if self._rec_visible else "  REC"
        rec_color = QColor(255, 40, 40, 240) if self._rec_visible else QColor(255, 40, 40, 40)
        painter.setPen(rec_color)
        painter.drawText(pad + 15, pad + 30, rec_text)

        painter.setPen(QColor(255, 110, 0, 210))
        painter.drawText(pad + 85, pad + 30, "SYS_CAM: DINO_POV_HD")

        energy_pct = 95 - int(self._flicker_timer * 1.5) % 25
        energy_bars = "|" * int(energy_pct / 10)
        energy_empty = " " * (10 - len(energy_bars))
        painter.drawText(w - pad - 280, pad + 30, "DINO_CORE: ACTIVE_OS")
        painter.drawText(w - pad - 280, pad + 50, f"BATTERY: [{energy_bars}{energy_empty}] {energy_pct}%")

        rx, ry, rh = 2.0, 4.0, 180.0
        main_win = getattr(self, "main_win", None)
        if main_win and hasattr(main_win, "panda_app") and main_win.panda_app:
            app_inst = main_win.panda_app
            if hasattr(app_inst, "battle") and app_inst.battle and app_inst.battle.player_robot:
                robot = app_inst.battle.player_robot
                rx = robot.v_tx
                ry = robot.v_ty
                rh = robot.v_h

        painter.drawText(pad + 15, h - pad - 45, f"COORD_X: {rx:.3f}")
        painter.drawText(pad + 15, h - pad - 25, f"COORD_Y: {ry:.3f}")

        painter.setPen(QColor(255, 110, 0, 210))
        painter.setFont(font_hud)
        painter.drawText(w - pad - 360, h - pad - 25, f"STEER: ACTIVE [YAW_ANGLE={rh:.1f}°]")

        painter.end()
