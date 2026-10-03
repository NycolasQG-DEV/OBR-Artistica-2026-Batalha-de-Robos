#!/usr/bin/env python3
"""Robot Arena 3D — Entry Point with Native PySide6 UI.

Panda3D is embedded as a child window inside a PySide6 central widget container,
with floating HUD overlays.
"""
import sys

import os

# Garante que o diretório de trabalho é o local do main.py para que caminhos relativos (assets/...) funcionem
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Disable Qt's high-DPI scaling before importing PySide6
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

from PySide6.QtCore import Qt, QCoreApplication, QTimer, QPoint, QEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QFrame, QLabel

from engine.platform.window_bootstrap import WindowBootstrapMixin
from engine.platform.camera_detection import detect_camera_index
from engine.platform.win32_window import force_foreground_simple
from engine.app_core import RobotArena3D

from game.screens.battle_screen import BattleScreen
from game.screens.character_select_screen import CharacterSelectScreen
from ui.hud import (
    BossHPBarOverlay, PlayerHUDOverlay, ActionsHUDOverlay, CVCursorWidget,
    MinigameInstructionOverlay, AttackMinigameOverlay, RoboticVisionOverlay,
    DodgeMinigameOverlay, DebugOverlay
)
from ui.hud.overlay_manager import OverlayManager
from ui.hud.hud_mode_transitions import HUDModeTransitions
from ui.input.cv_cursor_router import CVCursorRouter
from ui.hud.hud_scaling import compute_ui_scale



class GameWindow(QMainWindow, WindowBootstrapMixin):
    """Main window: embeds Panda3D and hosts native floating HUD overlays."""

    def __init__(self):
        super().__init__()
        
        # 1. Setup window properties, flags and fullscreen layout via bootstrap mixin
        self.setup_bootstrap()

        self.panda_app = None
        self._first_attack_reached = False
        self._hovered_widget = None
        self._hover_start_time = None
        self._prev_hand_closed = False

        from game.screens.game_over_screen import GameOverScreen

        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        # HUD transitions expect selection at index 0 and battle at index 1.
        self.select_screen = CharacterSelectScreen(self, self)
        self.select_screen.robot_chosen.connect(self._on_robot_chosen)
        self.stacked_widget.addWidget(self.select_screen)  # index 0
        self.panda_container = BattleScreen(self)
        self.stacked_widget.addWidget(self.panda_container)  # index 1
        self.stacked_widget.setCurrentWidget(self.panda_container)

        # Floating HUD Overlays
        self.boss_hp_overlay = BossHPBarOverlay(self)
        self.boss_hp_overlay.hide()

        self.player_hud_overlay = PlayerHUDOverlay(self)
        self.player_hud_overlay.hide()

        self.actions_overlay = ActionsHUDOverlay(self)
        self.actions_overlay.action_clicked.connect(self._on_action_clicked)
        self.actions_overlay.hide()

        self.minigame_instruction_overlay = MinigameInstructionOverlay(self)
        self.minigame_instruction_overlay.hide()

        self.attack_minigame_overlay = AttackMinigameOverlay(self)
        self.attack_minigame_overlay.hide()

        self.dodge_minigame_overlay = DodgeMinigameOverlay(self)
        self.dodge_minigame_overlay.hide()

        self.robotic_vision_overlay = RoboticVisionOverlay(self)
        self.robotic_vision_overlay.hide()

        # Debug overlay (Ctrl+D / F12): ângulo relativo/tarado dos robôs
        self.debug_overlay = DebugOverlay(self)
        self.debug_overlay.hide()
        self._debug_overlay_visible = False

        # Cinematic Overlays
        self.cinema_top = QFrame(self)
        self.cinema_top.main_win = self
        self.cinema_top.setStyleSheet("background-color: black; border: none;")
        self.cinema_top.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.cinema_top.hide()

        self.cinema_bottom = QFrame(self)
        self.cinema_bottom.main_win = self
        self.cinema_bottom.setStyleSheet("background-color: black; border: none;")
        self.cinema_bottom.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.cinema_bottom.hide()

        # Banner overlay
        self.banner_overlay = QLabel(self)
        self.banner_overlay.main_win = self
        self.banner_overlay.setAlignment(Qt.AlignCenter)
        self.banner_overlay.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.banner_overlay.setAttribute(Qt.WA_TranslucentBackground)
        self.banner_overlay.hide()

        # Computer Vision Gesture Cursor
        self.cv_cursor = CVCursorWidget(self)

        # 2. Instantiate managers
        self.overlay_manager = OverlayManager(self)
        self.hud_mode_transitions = HUDModeTransitions(self)
        self.cv_cursor_router = CVCursorRouter(self)

        # 3. Init Panda3D window (using physical size mapping from bootstrap mixin)
        pw, ph = self.init_panda_window()

        self.panda_app = RobotArena3D(
            parent_hwnd=int(self.panda_container.winId()),
            win_size=(pw, ph),
        )
        self.panda_app.qt_win = self
        self.panda_app.setup_screens()

        self.stacked_widget.setCurrentWidget(self.panda_container)
        QApplication.processEvents()

        # Start deferred synchronizations to align windows properly
        self.start_deferred_sync()

        # ── Timer periódico para manter overlays sempre no topo (z-order fix) ──
        # O Panda3D pode tomar o foco da janela e enterrar os overlays Qt abaixo
        # dele. Este timer garante que todos os overlays visíveis sejam re-elevados
        # a cada 500ms, independente do estado do CV ou interação do usuário.
        self._raise_overlays_timer = QTimer(self)
        self._raise_overlays_timer.setInterval(150)
        self._raise_overlays_timer.timeout.connect(self._periodic_raise_overlays)
        self._raise_overlays_timer.start()

    # ── Callbacks ─────────────────────────────────────────────────────

    def _on_robot_chosen(self, name):
        """Starts the battle with the selected champion."""
        if not self.panda_app or self.panda_app.battle.player_robot:
            return
        from settings import ROBOT_OPTIONS
        opt = next((o for o in ROBOT_OPTIONS if o["name"].lower() == name.lower()), None)
        if opt is None:
            raise ValueError(f"Robô desconhecido: {name}")
        self.stacked_widget.setCurrentWidget(self.panda_container)
        QApplication.processEvents()
        self.panda_app._on_robot_selected(opt)

    def _on_action_clicked(self, key):
        self._hovered_widget = None
        self._hover_start_time = None
        self.cv_cursor.set_cursor_state(None, None, 0.0, False)
        if self.panda_app:
            self.panda_app._on_action_selected(key)

    # ── Forwarding / Delegating methods ───────────────────────────────

    def _periodic_raise_overlays(self):
        """Re-eleva periodicamente todos os overlays visíveis no topo da z-order.
        Corrige bug do Windows onde o Panda3D enterra os overlays Qt quando ganha foco.
        """
        self.overlay_manager.raise_overlays()

    def _reposition_overlays(self):
        self.overlay_manager.reposition_overlays()

    def raise_overlays(self):
        self.overlay_manager.raise_overlays()

    def _show_battle_overlays(self):
        self.overlay_manager.show_battle_overlays()

    def _hide_all_overlays(self):
        self.overlay_manager.hide_all_overlays()

    def _hide_all_overlays_temporarily(self):
        self.overlay_manager.hide_all_overlays_temporarily()

    def _restore_all_overlays_after_minimize(self):
        self.overlay_manager.restore_all_overlays_after_minimize()

    def update_game_state(self, state_data):
        self.overlay_manager.update_game_state(state_data)

    def show_banner(self, text, color_hex="#ffcc00", duration=2.0, font_size_mult=1.0, pos_y_ratio=0.25):
        self.overlay_manager.show_banner(text, color_hex, duration, font_size_mult, pos_y_ratio)

    def show_sub_banner(self, text, color_hex="#ffffff", duration=2.0, font_size_mult=1.0, pos_y_ratio=0.18):
        self.overlay_manager.show_sub_banner(text, color_hex, duration, font_size_mult, pos_y_ratio)

    def show_cinematic_bars(self, show: bool):
        self.overlay_manager.show_cinematic_bars(show)

    def show_robotic_vision(self, show: bool):
        self.overlay_manager.show_robotic_vision(show)

    # ── HUD Mode transitions delegation ───────────────────────────────

    def define_hud(self, hud_name, transition=0.5):
        self.hud_mode_transitions.define_hud(hud_name, transition)

    def animate_player_hud(self, to_selection: bool):
        self.hud_mode_transitions.animate_player_hud(to_selection)

    def set_webcam_mode(self, mode):
        self.hud_mode_transitions.set_webcam_mode(mode)

    def enter_selection_hud_mode(self):
        self.hud_mode_transitions.enter_selection_hud_mode()

    def exit_selection_hud_mode(self):
        self.hud_mode_transitions.exit_selection_hud_mode()

    def enter_minigame_hud_mode(self, attack_dir):
        self.hud_mode_transitions.enter_minigame_hud_mode(attack_dir)

    def _reveal_minigame(self):
        self.hud_mode_transitions._reveal_minigame()

    def exit_minigame_hud_mode(self):
        self.hud_mode_transitions.exit_minigame_hud_mode()

    def enter_attack_minigame_hud_mode(self, minigame):
        self.hud_mode_transitions.enter_attack_minigame_hud_mode(minigame)

    def _start_attack_minigame_gameplay(self, minigame):
        self.hud_mode_transitions._start_attack_minigame_gameplay(minigame)

    def exit_attack_minigame_hud_mode(self):
        self.hud_mode_transitions.exit_attack_minigame_hud_mode()

    # ── Input routing delegation ──────────────────────────────────────

    def update_cv_cursor(self, nx, ny, closed, hands_data=None):
        self.cv_cursor_router.update_cv_cursor(nx, ny, closed, hands_data)

    # ── Helper methods ────────────────────────────────────────────────

    def get_player_hud_target(self, mode=None):
        if not hasattr(self, "panda_container"):
            return QPoint(14, 14)

        if self.panda_container.isVisible():
            geom = self.panda_container.geometry()
            origin = self.panda_container.mapToGlobal(QPoint(0, 0))
        else:
            geom = self.geometry()
            origin = self.mapToGlobal(QPoint(0, 0))

        vw = geom.width()
        vh = geom.height()

        scale = compute_ui_scale(vw, vh)

        px = origin.x() + int(14 * scale)
        py = origin.y() + int(14 * scale)
        return QPoint(px, py)

    def update_webcam_frame(self, rgb_bytes, w, h):
        self.player_hud_overlay.webcam.update_frame(rgb_bytes, w, h)
        if getattr(self.player_hud_overlay, "_minigame_active", False):
            hold_time = 0.0
            if self.panda_app and hasattr(self.panda_app, "hud") and hasattr(self.panda_app.hud, "_dodge_safe_time"):
                hold_time = self.panda_app.hud._dodge_safe_time
            self.player_hud_overlay.update_minigame_overlays(hold_time)

    def set_buttons_enabled(self, enabled):
        self.actions_overlay.set_buttons_enabled(enabled)

    def set_turn_timer_pct(self, frac):
        self.actions_overlay.set_turn_timer_pct(frac)
        if hasattr(self.player_hud_overlay, "minigame_timer_bar"):
            self.player_hud_overlay.minigame_timer_bar.setValue(int(frac * 100))

    def show_select_screen(self):
        """Shows both champions for standalone play and game resets."""
        self.stacked_widget.setCurrentWidget(self.select_screen)
        self.select_screen.on_enter()

    # ── Debug overlay (Ctrl+D / F12) ────────────────────────────────────

    def toggle_debug_overlay(self):
        self._debug_overlay_visible = not getattr(self, "_debug_overlay_visible", False)
        if self._debug_overlay_visible:
            self._position_debug_overlay()
            self.debug_overlay.show()
            self.debug_overlay.raise_()
        else:
            self.debug_overlay.hide()

    def _position_debug_overlay(self):
        if self.panda_container.isVisible():
            origin = self.panda_container.mapToGlobal(QPoint(0, 0))
        else:
            origin = self.mapToGlobal(QPoint(0, 0))
        self.debug_overlay.move(origin.x() + 16, origin.y() + 16)

    def update_debug_overlay(self):
        if not getattr(self, "_debug_overlay_visible", False):
            return
        if not self.panda_app or not self.panda_app.battle:
            return
        pr = self.panda_app.battle.player_robot
        ia = self.panda_app.battle.ia_robot
        if not pr or not ia:
            return
        self.debug_overlay.set_values(
            pr.name_code.upper(), pr.debug_relative_angle,
            ia.name_code.upper(), ia.debug_relative_angle,
        )

    # ── Overridden Events ─────────────────────────────────────────────

    def moveEvent(self, event):
        super().moveEvent(event)
        QTimer.singleShot(0, self._reposition_overlays)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._reposition_overlays)
        self.bootstrap_resize_event(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                self._hide_all_overlays_temporarily()
            else:
                self._restore_all_overlays_after_minimize()
        elif event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.raise_overlays()
        super().changeEvent(event)

    def keyPressEvent(self, event):
        if not self.bootstrap_key_event(event):
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.cv_cursor.close()
        self.cinema_top.close()
        self.cinema_bottom.close()
        self.banner_overlay.close()
        self.boss_hp_overlay.close()
        self.player_hud_overlay.close()
        self.debug_overlay.close()
        self.actions_overlay.close()
        self.attack_minigame_overlay.close()
        if self.panda_app:
            try:
                self.panda_app.destroy()
            except Exception:
                pass
        try:
            from game.combat.serial_controller import get_serial_controller
            get_serial_controller().close()
        except Exception:
            pass
        super().closeEvent(event)
        sys.exit(0)



if __name__ == "__main__":
    import argparse
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    # ── Argumento CLI: --robot <nome> (sem argumento, mostra seleção) ────────
    # Uso: python main.py --robot PenLinux
    #       python main.py --robot DinoByte
    parser = argparse.ArgumentParser(description="Robot Arena 3D")
    parser.add_argument(
        "--robot",
        type=str,
        default=None,
        required=False,
        choices=["DinoByte", "PenLinux", "dinobyte", "penlinux"],
        help="Robô escolhido para a batalha (DinoByte ou PenLinux; sem opção, mostra seleção)",
    )
    args, _unknown = parser.parse_known_args()
    chosen_robot = args.robot
    print(f"[main.py] Robô selecionado: {chosen_robot or 'aguardando escolha'}")

    q_app = QApplication(sys.argv)

    # Exige que a conexão serial com o ESP32 esteja 100% estabelecida antes de iniciar o jogo
    from ui.serial_connection_dialog import ensure_serial_connected_before_start
    if not ensure_serial_connected_before_start():
        print("[main.py] Conexão serial não estabelecida. Encerrando aplicação.")
        sys.exit(0)

    win = GameWindow()

    # Wait for Panda3D's first frame before the selected champion enters.
    if chosen_robot:
        QTimer.singleShot(300, lambda: win._on_robot_chosen(chosen_robot))
    else:
        QTimer.singleShot(300, win.show_select_screen)

    panda_timer = QTimer()
    panda_timer.setInterval(0)
    panda_timer.timeout.connect(win.panda_app.taskMgr.step)
    panda_timer.start()

    def _final_foreground():
        force_foreground_simple(int(win.winId()))
    QTimer.singleShot(300, _final_foreground)

    sys.exit(q_app.exec())
