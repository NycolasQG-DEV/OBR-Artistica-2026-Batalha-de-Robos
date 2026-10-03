# ui/hud/actions_hud.py — Tela de seleção de ataque (overlay preto translúcido, mão SVG e preenchimento circular suave ao detectar)
import time
import random
from PySide6.QtCore import Qt, Signal, QRectF, QByteArray, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QPushButton,
    QGraphicsDropShadowEffect, QWidget
)
from PySide6.QtSvg import QSvgRenderer
from ui.hud.design_system import *
from ui.hud.svg_icons import SVG_HAND_OPEN
from ui.hud.lever_canvas import LeverCanvas


class ActionsHUDOverlay(QFrame):
    """
    HUD de Seleção de Ataque:
    - Overlay preto translúcido com card escuro opaco.
    - Ícone de mão SVG no centro (sem furos na renderização).
    - Período de carência de 0.8s ao abrir para evitar auto-confirmação.
    - Exige 3.0s contínuos de mão aberta detectada na câmera.
    - Animação de progresso circular neon e contagem regressiva.
    """
    action_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

        self.lever_pulled = False
        self.used_attacks = []
        self.target_action = None
        self.robot_attacks = []
        self.attack_meta = {}

        self._detect_start_time = None
        self._detect_animating = False
        self._last_sec_str = ""
        self._enable_time = 0.0  # Trava de carência inicial ao abrir
        self.FILL_DURATION = 3.0  # Exige 3.0 segundos de mão detectada na câmera

        # Renderer SVG
        self._hand_svg_data = QByteArray(SVG_HAND_OPEN.encode('utf-8'))
        self._hand_renderer = QSvgRenderer(self._hand_svg_data)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        # Card central com design premium
        self.card = QFrame(self)
        self.card.setFixedSize(540, 430)
        self.card.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)



        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        # Título instrução principal
        self.lbl_title = QLabel("ESTENDA A MÃO PARA A TELA POR 3s", self.card)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 20px;
            font-weight: 900;
            color: #00ecff;
            background: transparent;
            border: none;
            letter-spacing: 1.5px;
        """)
        
        shadow_title = QGraphicsDropShadowEffect(self)
        shadow_title.setBlurRadius(8)
        shadow_title.setColor(QColor(0, 0, 0, 255))
        shadow_title.setOffset(2, 2)
        self.lbl_title.setGraphicsEffect(shadow_title)
        
        card_layout.addWidget(self.lbl_title)

        # Canvas da alavanca com o símbolo da mão no centro
        self._lever_canvas = LeverCanvas(self._hand_renderer, self.card)
        self._lever_canvas.auto_pull_triggered.connect(self._trigger_hand_confirm)
        self._lever_canvas.setFixedSize(180, 250)
        card_layout.addWidget(self._lever_canvas, 0, Qt.AlignCenter)

        # Subtítulo instrução
        self.lbl_sub = QLabel("MANTENHA A MÃO EM FRENTE À CÂMERA POR 3 SECUNDOS", self.card)
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 13px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.85);
            background: transparent;
            border: none;
        """)
        
        shadow_sub = QGraphicsDropShadowEffect(self)
        shadow_sub.setBlurRadius(5)
        shadow_sub.setColor(QColor(0, 0, 0, 255))
        shadow_sub.setOffset(1, 1)
        self.lbl_sub.setGraphicsEffect(shadow_sub)
        
        card_layout.addWidget(self.lbl_sub)

        # Botão manual (para fallback de clique por mouse)
        self.btn_confirm = QPushButton("INICIAR ATAQUE", self.card)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setFixedHeight(46)
        self.btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00ecff, stop:1 #0077ff);
                color: #ffffff;
                font-family: {FONT_HUD};
                font-size: 16px;
                font-weight: 900;
                border: 2px solid rgba(255,255,255,0.4);
                border-radius: 18px;
                padding: 0 32px;
                letter-spacing: 1.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33f0ff, stop:1 #3399ff);
                border: 2px solid #00ecff;
            }}
        """)
        self.btn_confirm.clicked.connect(self._trigger_hand_confirm)
        card_layout.addWidget(self.btn_confirm, 0, Qt.AlignCenter)

        layout.addWidget(self.card, 0, Qt.AlignCenter)

    def _reset_state(self):
        self._lever_state = 0
        self._lever_start_ny = 0.0
        self._lever_pull_dist = 0.40
        self.lbl_title.setText("PUXE A ALAVANCA PARA INICIAR")
        self.lbl_title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 20px;
            font-weight: 900;
            color: #00ecff;
            background: transparent;
            border: none;
            letter-spacing: 1.5px;
        """)
        self.lbl_sub.setText("FECHE A MÃO E PUXE PARA BAIXO")
        self._lever_canvas.reset()
        self._lever_canvas.show()
        self.btn_confirm.show()

    def reveal_jackpot(self):
        """Exibe a tela de seleção de ação e impõe carência inicial de 0.8s."""
        self.lever_pulled = False
        self.target_action = None
        self._reset_state()

        # Trava de carência: ignora gestos durante 0.8s após o modal abrir para impedir auto-confirmação
        self._enable_time = time.time() + 0.8
        self._roulette_timer = QTimer(self)
        self._roulette_timer.timeout.connect(self._on_roulette_tick)
        self._roulette_ticks = 0

        battle = None
        if self.main_win and self.main_win.panda_app and self.main_win.panda_app.battle:
            battle = self.main_win.panda_app.battle
            if battle and battle.player_robot:
                self.robot_attacks = battle.player_robot.ATTACKS
                self.attack_meta = battle.player_robot.ATTACK_META

        if battle and battle.player_robot:
            pr = battle.player_robot
            self.target_action = pr.get_next_available_attack()
            pr.record_attack_used(self.target_action)
            self.used_attacks = list(getattr(pr, "used_attack_keys", []))
        else:
            available = [f"atk{i}" for i in range(len(self.robot_attacks))] if self.robot_attacks else ["atk0", "atk1", "atk2"]
            remaining = [a for a in available if a not in self.used_attacks]
            if not remaining:
                self.used_attacks = []
                remaining = list(available)
            self.target_action = random.choice(remaining) if remaining else "atk0"
            self.used_attacks.append(self.target_action)

        self.show()
        self.raise_()
        self.activateWindow()

    def _trigger_hand_confirm(self):
        """Starts the roulette animation before emitting."""
        if self.lever_pulled:
            return
        self.lever_pulled = True
        self.lbl_sub.setText("SORTEANDO ATAQUE...")
        self.lbl_title.setStyleSheet("font-family: 'Segoe UI'; font-size: 32px; font-weight: 900; color: #ffaa00; background: transparent; border: none; letter-spacing: 2px;")
        self._lever_canvas.hide()
        self.btn_confirm.hide()
        
        self._roulette_ticks = 0
        self._roulette_timer.start(80)

    def _on_roulette_tick(self):
        self._roulette_ticks += 1
        
        if self._roulette_ticks < 20:
            # Animate choices
            if self.robot_attacks:
                random_atk = random.choice(self.robot_attacks)
                meta = self.attack_meta.get(random_atk, {})
                self.lbl_title.setText(meta.get("name", "ATAQUE").upper())
            else:
                self.lbl_title.setText(random.choice(["ATAQUE A", "ATAQUE B", "ATAQUE C"]))
        else:
            self._roulette_timer.stop()
            
            # Show final action
            if self.target_action:
                idx = int(self.target_action[-1])
                if self.robot_attacks and idx < len(self.robot_attacks):
                    final_atk = self.robot_attacks[idx]
                    meta = self.attack_meta.get(final_atk, {})
                    self.lbl_title.setText(meta.get("name", "ATAQUE").upper())
                    self.lbl_title.setStyleSheet("font-family: 'Segoe UI'; font-size: 28px; font-weight: 900; color: #00ff00; background: transparent; border: none; letter-spacing: 2px;")
                    self.lbl_sub.setText("ATAQUE SELECIONADO!")
            
            # Wait 1s and emit
            QTimer.singleShot(1000, self._finish_and_emit)
            
    def _finish_and_emit(self):
        self.hide()
        if self.target_action:
            self.action_clicked.emit(self.target_action)

    def dismiss(self):
        if self.isVisible():
            self._trigger_hand_confirm()

    def update_cv_gesture(self, nx, ny, closed):
        """
        Gesto de puxar a alavanca: fechar a mão e mover para baixo.
        """
        if self.lever_pulled:
            return

        # Respeita o tempo de carência inicial ao abrir a tela
        if time.time() < self._enable_time:
            return

        hand_detected = (nx is not None and ny is not None)

        if not hand_detected:
            if getattr(self, "_lever_state", 0) != 0:
                self._reset_state()
            return

        if not hasattr(self, "_lever_state"):
            self._reset_state()

        if self._lever_state == 0:
            if not closed:
                # Mão aberta detectada
                self.lbl_title.setText("PUXE A ALAVANCA PARA INICIAR")
                self.lbl_sub.setText("FECHE A MÃO E PUXE PARA BAIXO")
                self._lever_canvas.set_progress(0.0, False)
            else:
                # Mão fechou, inicia a puxada
                self._lever_state = 1
                self._lever_start_ny = ny
                self.lbl_title.setText("PUXANDO ALAVANCA...")
                self._lever_canvas.set_progress(0.0, True)

        elif self._lever_state == 1:
            if not closed:
                # Mão abriu no meio do movimento
                self._reset_state()
            else:
                # Calcula o movimento para baixo (ny cresce para baixo)
                delta_y = ny - self._lever_start_ny
                pct = max(0.0, min(100.0, (delta_y / self._lever_pull_dist) * 100.0))
                
                self._lever_canvas.set_progress(pct, True)
                self.lbl_sub.setText(f"DESCENDO... {int(pct)}%")

                if pct >= 100.0:
                    self._trigger_hand_confirm()

    def scale_ui(self, scale):
        w = int(540 * scale)
        h = int(430 * scale)
        self.card.setFixedSize(w, h)
        lv_w = int(180 * scale)
        lv_h = int(250 * scale)
        self._lever_canvas.setFixedSize(lv_w, lv_h)

    def set_buttons_enabled(self, enabled):
        pass

    def set_turn_timer_pct(self, frac):
        pass



