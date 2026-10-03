# ui/hud/dodge_overlay.py — overlay de pintura e renderização do minigame de desvio (Dodge)
import math
import time
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QLinearGradient
from PySide6.QtWidgets import QFrame
from ui.hud.design_system import FONT_HUD
from settings import MINIGAME_DURATION

class DodgeMinigameOverlay(QFrame):
    """Fullscreen overlay that renders the dodge minigame interface in Qt.
    
    Includes 4 creative variants: Left/Right Side, Circular, Up/Down, and Chaos Grid.
    It reads head coordinates from CV input and displays real-time instructions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
        self._scale = 1.0

        # Repaint timer (~30 FPS paint)
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(33)
        self._paint_timer.timeout.connect(self.update)

    def mouseMoveEvent(self, event):
        w = max(1, self.width())
        h = max(1, self.height())
        pos = event.position() if hasattr(event, "position") else event.pos()
        nx = max(0.0, min(1.0, pos.x() / w))
        ny = max(0.0, min(1.0, pos.y() / h))
        if self.main_win and hasattr(self.main_win, "panda_app") and self.main_win.panda_app:
            app = self.main_win.panda_app
            app._input_mode = "mouse"
            app._finger_pos_norm = (nx, ny)
            if hasattr(app, "battle") and app.battle:
                app.battle.last_known_face_x = nx
                app.battle.last_known_face_y = ny
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        w = max(1, self.width())
        h = max(1, self.height())
        pos = event.position() if hasattr(event, "position") else event.pos()
        nx = max(0.0, min(1.0, pos.x() / w))
        ny = max(0.0, min(1.0, pos.y() / h))
        if self.main_win and hasattr(self.main_win, "panda_app") and self.main_win.panda_app:
            app = self.main_win.panda_app
            from game.combat.battle_logic import STATE_MINIGAME
            if hasattr(app, "battle") and app.battle and app.battle.state == STATE_MINIGAME:
                attack_dir = getattr(app.battle, "minigame_attack_dir", "left")
                if attack_dir == "left":
                    chosen = "right" if nx >= 0.75 else "left"
                else:
                    chosen = "left" if nx <= 0.25 else "right"
                app.battle.resolve_minigame(chosen)
        super().mousePressEvent(event)

    def start_painting(self):
        if not self._paint_timer.isActive():
            self._paint_timer.start()
        self.show()
        self.raise_()

    def stop_painting(self):
        self._paint_timer.stop()
        self.hide()

    def scale_ui(self, scale):
        self._scale = scale

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        scale = self._scale

        # 1. Background: retrieve current webcam feed (ultra-lightweight cached pixmap)
        webcam = None
        if self.main_win and hasattr(self.main_win, "player_hud_overlay") and self.main_win.player_hud_overlay:
            webcam = self.main_win.player_hud_overlay.webcam

        drawn_webcam = False
        if webcam:
            minigame_pix = getattr(webcam, "_cached_minigame_pix", None)
            if minigame_pix and not minigame_pix.isNull():
                painter.setOpacity(0.35)
                painter.drawPixmap(0, 0, w, h, minigame_pix)
                painter.setOpacity(1.0)
                drawn_webcam = True
        
        if not drawn_webcam:
            painter.fillRect(0, 0, w, h, QColor(10, 14, 26, 120))
        
        painter.fillRect(0, 0, w, h, QColor(2, 6, 14, 80))

        # Check if game state is active minigame
        battle = None
        if self.main_win and hasattr(self.main_win, "panda_app") and self.main_win.panda_app:
            app_inst = self.main_win.panda_app
            if hasattr(app_inst, "battle"):
                battle = app_inst.battle

        if not battle:
            painter.end()
            return

        # Extract minigame variables
        variant = getattr(battle, "dodge_variant", 0)
        attack_dir = getattr(battle, "minigame_attack_dir", "left")
        start_time = getattr(battle, "minigame_start_time", time.time())
        elapsed = time.time() - start_time

        # Extract player head/pointer coordinates (suporta mouse e CV em tempo real)
        face_x, face_y = None, None
        
        # 1. Priorize a coordenada armazenada na batalha (que é atualizada via mouseMoveEvent ou game_loop)
        if battle and hasattr(battle, "last_known_face_x"):
            face_x = getattr(battle, "last_known_face_x", None)
            face_y = getattr(battle, "last_known_face_y", 0.5)

        # 2. Fallback para _finger_pos_norm no Panda3D
        if face_x is None and self.main_win and hasattr(self.main_win, "panda_app") and self.main_win.panda_app:
            finger_pos = getattr(self.main_win.panda_app, "_finger_pos_norm", None)
            if finger_pos and finger_pos[0] is not None and finger_pos[1] is not None:
                face_x, face_y = finger_pos

        # 3. Fallback direto para cv_input com API de cabeça padronizada
        if face_x is None and self.main_win and hasattr(self.main_win, "cv_input") and self.main_win.cv_input:
            cv = self.main_win.cv_input
            if hasattr(cv, "get_head_position"):
                face_x, face_y = cv.get_head_position()
            else:
                face_x = getattr(cv, "face_x", 0.5)
                face_y = getattr(cv, "face_y", 0.5)

        if face_x is None:
            face_x, face_y = 0.5, 0.5

        # Draw minimalist danger/safe UI (Variant 0)
        if variant == 0:
            is_left_danger = (attack_dir == "left")
            
            # Subtle edge vignette instead of solid boxes
            danger_grad = QLinearGradient(0, 0, w//3, 0) if is_left_danger else QLinearGradient(w, 0, w - w//3, 0)
            pulse_alpha = 40 + int(20 * math.sin(elapsed * 8.0))
            danger_grad.setColorAt(0, QColor(255, 0, 0, pulse_alpha))
            danger_grad.setColorAt(1, QColor(255, 0, 0, 0))
            painter.fillRect(0, 0, w, h, danger_grad)

            safe_grad = QLinearGradient(w, 0, w - w//3, 0) if is_left_danger else QLinearGradient(0, 0, w//3, 0)
            safe_grad.setColorAt(0, QColor(0, 255, 120, 30))
            safe_grad.setColorAt(1, QColor(0, 255, 120, 0))
            painter.fillRect(0, 0, w, h, safe_grad)

            # Clean central instruction text
            font_title = QFont(FONT_HUD, int(40 * scale), QFont.Black)
            painter.setFont(font_title)
            
            safe_arrow = "DESVIE PARA A DIREITA >>>" if is_left_danger else "<<< DESVIE PARA A ESQUERDA"
            
            # Draw shadow
            painter.setPen(QColor(0, 0, 0, 200))
            painter.drawText(QRect(2, 2, w, h), Qt.AlignCenter, safe_arrow)
            
            # Draw text
            painter.setPen(QColor(0, 255, 120, 255))
            painter.drawText(QRect(0, 0, w, h), Qt.AlignCenter, safe_arrow)
            
            # Draw time remaining at the bottom
            font_time = QFont(FONT_HUD, int(24 * scale), QFont.Bold)
            painter.setFont(font_time)
            rem_time = max(0.0, 3.0 - elapsed)
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(QRect(0, h - int(100 * scale), w, int(100 * scale)), Qt.AlignCenter, f"{rem_time:.1f}s")
            
            # Progress bar for holding the position
            safe_time = getattr(battle, "dodge_safe_time", 0.0)
            if safe_time > 0:
                pct = min(1.0, safe_time / 0.75)
                bar_w = int(300 * scale)
                bar_h = int(12 * scale)
                bx = (w - bar_w) // 2
                by = (h // 2) + int(50 * scale)
                
                # Background
                painter.fillRect(bx, by, bar_w, bar_h, QColor(0, 0, 0, 150))
                # Fill
                painter.fillRect(bx, by, int(bar_w * pct), bar_h, QColor(0, 255, 120, 255))


        elif variant == 1:
            # Clean central instruction for Dance Night
            font_title = QFont(FONT_HUD, int(35 * scale), QFont.Black)
            painter.setFont(font_title)
            
            # Shadow
            painter.setPen(QColor(0, 0, 0, 200))
            painter.drawText(QRect(2, 2, w, h), Qt.AlignCenter, "FIQUE PARADO NO CENTRO")
            
            # Text
            painter.setPen(QColor(0, 255, 255, 255))
            painter.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "FIQUE PARADO NO CENTRO")
            
            # Draw time remaining at the bottom
            font_time = QFont(FONT_HUD, int(24 * scale), QFont.Bold)
            painter.setFont(font_time)
            rem_time = max(0.0, 3.0 - elapsed)
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(QRect(0, h - int(100 * scale), w, int(100 * scale)), Qt.AlignCenter, f"{rem_time:.1f}s")
            
            # Progress bar for holding the position
            safe_time = getattr(battle, "dodge_safe_time", 0.0)
            if safe_time > 0:
                pct = min(1.0, safe_time / 0.75)
                bar_w = int(300 * scale)
                bar_h = int(12 * scale)
                bx = (w - bar_w) // 2
                by = (h // 2) + int(50 * scale)
                
                # Background
                painter.fillRect(bx, by, bar_w, bar_h, QColor(0, 0, 0, 150))
                # Fill
                painter.fillRect(bx, by, int(bar_w * pct), bar_h, QColor(0, 255, 255, 255))

        elif variant == 2:
            is_top_danger = (attack_dir == "left")
            danger_rect = QRect(0, 0, w, h // 2) if is_top_danger else QRect(0, h // 2, w, h // 2)
            safe_rect = QRect(0, h // 2, w, h // 2) if is_top_danger else QRect(0, 0, w, h // 2)

            pulse = 60 + int(45 * math.sin(elapsed * 8.0))
            painter.fillRect(danger_rect, QColor(220, 20, 20, pulse))

            painter.setPen(QPen(QColor(0, 255, 120, 160), 6 * scale))
            painter.setBrush(QColor(0, 255, 120, 15))
            painter.drawRect(safe_rect.adjusted(6, 6, -6, -6))

            font_title = QFont(FONT_HUD, int(26 * scale), QFont.Bold)
            painter.setFont(font_title)
            
            painter.setPen(QColor(255, 40, 40, 220))
            painter.drawText(danger_rect, Qt.AlignCenter, "[!] VARREDURA DO BOSS (PERIGO)")
            
            painter.setPen(QColor(0, 255, 120, 220))
            safe_action = "ABAIXE-SE AGORA!" if is_top_danger else "INCLINE-SE / LEVANTE-SE!"
            painter.drawText(safe_rect, Qt.AlignCenter, f"ZONA SEGURA\n{safe_action}")

        elif variant == 3:
            safe_quad = int(elapsed / 1.8) % 4
            
            qw = w // 2
            qh = h // 2
            tx = (safe_quad % 2) * qw
            ty = (safe_quad // 2) * qh

            if not hasattr(self, "_quad_x") or self._quad_x is None:
                self._quad_x = tx
                self._quad_y = ty
            else:
                self._quad_x += (tx - self._quad_x) * 0.22
                self._quad_y += (ty - self._quad_y) * 0.22

            safe_rect = QRect(int(self._quad_x), int(self._quad_y), qw, qh)

            pulse = 50 + int(20 * math.sin(elapsed * 6.0))
            painter.fillRect(0, 0, w, h, QColor(220, 20, 20, pulse))

            if drawn_webcam and minigame_pix:
                painter.drawPixmap(safe_rect, minigame_pix, safe_rect)
            else:
                painter.fillRect(safe_rect, QColor(4, 8, 16, 255))

            painter.fillRect(safe_rect, QColor(0, 255, 120, 40))
            painter.setPen(QPen(QColor(0, 255, 120, 180), 4 * scale))
            painter.drawRect(safe_rect.adjusted(4, 4, -4, -4))

            painter.setPen(QPen(QColor(255, 255, 255, 40), 2 * scale))
            painter.drawLine(w // 2, 0, w // 2, h)
            painter.drawLine(0, h // 2, w, h // 2)

            font_title = QFont(FONT_HUD, int(20 * scale), QFont.Bold)
            painter.setFont(font_title)

            quads = [
                QRect(0, 0, qw, qh),
                QRect(qw, 0, qw, qh),
                QRect(0, qh, qw, qh),
                QRect(qw, qh, qw, qh)
            ]
            for i, rect in enumerate(quads):
                if i != safe_quad:
                    painter.setPen(QColor(255, 40, 40, 150))
                    painter.drawText(rect, Qt.AlignCenter, "X BLOQUEADO")

            painter.setPen(QColor(0, 255, 120, 220))
            painter.drawText(safe_rect, Qt.AlignCenter, "AREA SEGURA!\nMOVA-SE PARA CA")

        # Draw head cursor
        if face_x is not None and face_y is not None:
            fx = int(face_x * w)
            fy = int(face_y * h)
            cursor_r = int(22 * scale)

            pulse_r = cursor_r + int(6 * abs(math.sin(time.time() * 10)))
            painter.setPen(QPen(QColor(0, 240, 255, 180), 2.5 * scale))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(fx, fy), pulse_r, pulse_r)

            painter.setPen(QPen(QColor(0, 240, 255, 220), 1.5 * scale))
            painter.drawLine(fx - pulse_r - 5, fy, fx + pulse_r + 5, fy)
            painter.drawLine(fx, fy - pulse_r - 5, fx, fy + pulse_r + 5)

            painter.setBrush(QBrush(QColor(0, 240, 255, 240)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(fx, fy), 5, 5)

            painter.setPen(QColor(0, 240, 255, 230))
            painter.setFont(QFont(FONT_HUD, int(12 * scale), QFont.Bold))
            painter.drawText(fx - 60, fy - pulse_r - 8, 120, 20, Qt.AlignCenter, "SUA CABEÇA")

        # Header Text
        font_banner = QFont(FONT_HUD, int(42 * scale), QFont.Bold)
        painter.setFont(font_banner)
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(0, int(54 * scale), w, int(60 * scale), Qt.AlignCenter, "ESQUIVE DO ATAQUE DO BOSS!")
        painter.setPen(QColor(255, 220, 0, 240))
        painter.drawText(0, int(50 * scale), w, int(60 * scale), Qt.AlignCenter, "ESQUIVE DO ATAQUE DO BOSS!")

        # Timer
        remaining = max(0.0, MINIGAME_DURATION - elapsed)
        font_metrics = QFont(FONT_HUD, int(16 * scale), QFont.Bold)
        painter.setFont(font_metrics)
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(w - int(240 * scale), int(45 * scale), f"TEMPO LIMITE: {remaining:.1f}s")

        # Bottom Evade Countdown Bar
        bar_w = int(500 * scale)
        bar_h = int(24 * scale)
        bx = (w - bar_w) // 2
        by = h - int(70 * scale)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 2 * scale))
        painter.setBrush(QBrush(QColor(25, 30, 45, 180)))
        painter.drawRoundedRect(bx, by, bar_w, bar_h, 8 * scale, 8 * scale)

        pct = max(0.0, min(100.0, (remaining / MINIGAME_DURATION) * 100.0))
        if pct > 0:
            fill_w = int(bar_w * (pct / 100.0))
            grad = QLinearGradient(bx, by, bx + fill_w, by)
            grad.setColorAt(0, QColor(0, 255, 120, 140))
            grad.setColorAt(1, QColor(0, 255, 120, 240))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(bx, by, fill_w, bar_h, 8 * scale, 8 * scale)

        font_bar = QFont(FONT_HUD, int(11 * scale), QFont.Bold)
        painter.setFont(font_bar)
        painter.setPen(QColor(255, 255, 255, 210))
        txt = "ESQUIVE! MOVA SUA CABEÇA PARA A ÁREA SEGURA"
        painter.drawText(bx, by, bar_w, bar_h, Qt.AlignCenter, txt)

        painter.end()
