# ui/hud/hud_integration.py — Integração do HUD Qt com o Panda3D
import time
from settings import (
    STATE_MINIGAME, PLAYER_TURN_TIMEOUT, MINIGAME_DURATION,
    STATE_PLAYER_TURN, C_ORANGE, C_GREEN, C_PURPLE, C_RED, C_YELLOW
)
from game.minigames import DodgeMinigame

class QtHUDIntegration:
    def __init__(self, base_app, battle):
        self.base = base_app
        self.battle = battle
        self.dodge_minigame = DodgeMinigame(self.base, self.battle)
        self._dodge_overlays = []
        self._dodge_danger_label = None
        self._dodge_safe_label = None
        self._dodge_arrow_label = None
        self._dodge_center_timer = None
        self._has_pushed_none_signal = False
        self._dodge_safe_time = 0.0
        
        # Keep dummy nodes to prevent crashes with timeline dependencies
        class DummyBG:
            def hide(self): pass
            def show(self): pass
            def setPos(self, *args): pass
        self._p_bg = DummyBG()
        self._boss_bg = DummyBG()
        self._portrait_bg = DummyBG()

    def update(self, dt, battle_log, action_hover, hover_timer, turn_start, finger_pos_norm, screen_w, screen_h):
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            pr = self.battle.player_robot
            ia = self.battle.ia_robot
            player_hp = pr.hp if pr else 100
            boss_hp = ia.hp if ia else 100
            player_name = pr.name_code.upper() if pr else "PENLINUX"
            boss_name = ia.name_code.upper() if ia else "DINOBYTE"
            
            player_status = []
            if pr and pr.is_defending:
                player_status.append("DEF")
            boss_status = []
            if ia and ia.is_defending:
                boss_status.append("DEF")

            logs_lines = [msg for msg, _ in self.base._battle_log[-8:]]
            
            state_data = {
                "player_hp": int(player_hp),
                "boss_hp": int(boss_hp),
                "player_name": player_name,
                "boss_name": boss_name,
                "player_status": "  ".join(player_status),
                "boss_status": "  ".join(boss_status),
                "turn": self.battle.turn_number,
                "round": self.battle.player_rounds,
                "logs": "<br>".join(logs_lines),
                "minigame_attack_dir": getattr(self.battle, "minigame_attack_dir", "left"),
                "match_time_remaining": self.battle.match_time_remaining
            }
            self.base.qt_win.update_game_state(state_data)

            # Debug overlay (Ctrl+D / F12): ângulo relativo/tarado dos robôs
            if hasattr(self.base.qt_win, "update_debug_overlay"):
                self.base.qt_win.update_debug_overlay()

            # Minigame dodge tracking (keep local math in Panda3D)
            
            # Check if Qt window is currently in the minigame intro instruction overlay
            intro_active = False
            if hasattr(self.base, "qt_win") and self.base.qt_win:
                if getattr(self.base.qt_win.player_hud_overlay, "_minigame_intro_active", False) or (
                    hasattr(self.base.qt_win, "minigame_instruction_overlay") and self.base.qt_win.minigame_instruction_overlay.isVisible()
                ):
                    intro_active = True

            if self.battle.state == STATE_MINIGAME and not getattr(self.battle, "minigame_choice", None):
                nx, ny = 0.5, 0.5
                if getattr(self.base, "_input_mode", "mouse") == "cv" and self.base.cv_input:
                    # Rastreio de rosto (head tracking)
                    face_x = getattr(self.base.cv_input, "face_x", None)
                    face_y = getattr(self.base.cv_input, "face_y", None)
                    if face_x is not None and face_y is not None:
                        nx, ny = face_x, face_y
                elif finger_pos_norm and finger_pos_norm[0] is not None and finger_pos_norm[1] is not None:
                    nx, ny = finger_pos_norm
                
                # Armazena a posição atual da cabeça para a decisão final no término do tempo
                self.battle.last_known_face_x = nx
                self.battle.last_known_face_y = ny
            else:
                if hasattr(self.battle, "minigame_current_side"):
                    self.battle.minigame_current_side = "center"

            # Flashing warning overlay in Panda3D viewport
            attack_dir = getattr(self.battle, "minigame_attack_dir", None)
            self.dodge_minigame.update_colors(attack_dir, intro_active)

            # Push webcam frame
            if self.base.cv_input:
                webcam_mode = getattr(self.base, "_webcam_mode", "hidden")
                if webcam_mode != "hidden":
                    current_time = time.time()
                    if not hasattr(self, "_last_webcam_push_time"):
                        self._last_webcam_push_time = 0.0
                    
                    if current_time - self._last_webcam_push_time >= 0.033:
                        raw_rgb = None
                        w_f, h_f = 0, 0
                        with self.base.cv_input._lock:
                            raw_rgb = self.base.cv_input.preview_rgb_bytes
                            w_f = self.base.cv_input.preview_w
                            h_f = self.base.cv_input.preview_h
                        
                        if raw_rgb is not None:
                            self.base.qt_win.update_webcam_frame(raw_rgb, w_f, h_f)
                            self._has_pushed_none_signal = False
                            self._last_webcam_push_time = current_time
                        else:
                            if not getattr(self, "_has_pushed_none_signal", False):
                                self.base.qt_win.update_webcam_frame(None, 0, 0)
                                self._has_pushed_none_signal = True
                            self._last_webcam_push_time = current_time
            else:
                if not getattr(self, "_has_pushed_none_signal", False):
                    if hasattr(self.base, "qt_win") and self.base.qt_win:
                        self.base.qt_win.update_webcam_frame(None, 0, 0)
                    self._has_pushed_none_signal = True

            # Update CV cursor
            face_active = False
            pose_active = False
            if self.base.cv_input:
                if getattr(self.base.cv_input, "face_detection_enabled", False):
                    face_active = True
                if getattr(self.base.cv_input, "pose_detection_enabled", False):
                    pose_active = True

            is_minigame_or_head = (self.battle.state == STATE_MINIGAME) or face_active or pose_active
            if is_minigame_or_head or not (finger_pos_norm and finger_pos_norm[0] is not None and finger_pos_norm[1] is not None):
                self.base.qt_win.update_cv_cursor(None, None, False, [])
            else:
                nx, ny = finger_pos_norm
                closed = False
                hands_data = []
                if self.base._input_mode == "cv" and self.base.cv_input:
                    closed = self.base.cv_input._hand_closed
                    hands_data = self.base.cv_input.get_hands_landmarks()
                else:
                    closed = getattr(self.base, "_mouse_pressed", False)
                self.base.qt_win.update_cv_cursor(nx, ny, closed, hands_data)

            # Update turn timer
            frac = 0.0
            state = self.battle.state
            if state == STATE_PLAYER_TURN and turn_start > 0:
                lever_pulled = False
                if self.base and hasattr(self.base, "qt_win") and self.base.qt_win and hasattr(self.base.qt_win, "actions_overlay"):
                    lever_pulled = getattr(self.base.qt_win.actions_overlay, "lever_pulled", False)
                
                if lever_pulled:
                    frac = 1.0
                else:
                    # Tempo infinito a pedido do jogador (barra sempre cheia)
                    frac = 1.0
            elif state == STATE_MINIGAME and self.battle.minigame_start_time > 0:
                # Get intro_active status from player_hud_overlay
                intro_active = False
                if hasattr(self.base, "qt_win") and self.base.qt_win:
                    if getattr(self.base.qt_win.player_hud_overlay, "_minigame_intro_active", False) or (
                        hasattr(self.base.qt_win, "minigame_instruction_overlay") and self.base.qt_win.minigame_instruction_overlay.isVisible()
                    ):
                        intro_active = True
                
                if intro_active:
                    frac = 1.0
                else:
                    elapsed = time.time() - self.battle.minigame_start_time
                    frac = max(0.0, (MINIGAME_DURATION - elapsed) / MINIGAME_DURATION)
            self.base.qt_win.set_turn_timer_pct(frac)

    def show_banner(self, text: str, color=None, duration=2.0, font_size_mult=1.0, pos_y_ratio=0.25, color_hex=None):
        if color is None and color_hex is not None:
            color = color_hex
        hex_color = "#ffcc00"
        if isinstance(color, str):
            hex_color = color
        elif color and (isinstance(color, list) or isinstance(color, tuple)):
            r = int(max(0.0, min(1.0, color[0])) * 255)
            g = int(max(0.0, min(1.0, color[1])) * 255)
            b = int(max(0.0, min(1.0, color[2])) * 255)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            self.base.qt_win.show_banner(text, hex_color, duration, font_size_mult, pos_y_ratio)

    def show_sub_banner(self, text: str, color=None, duration=2.0, font_size_mult=1.0, pos_y_ratio=0.18, color_hex=None):
        if color is None and color_hex is not None:
            color = color_hex
        hex_color = "#ffffff"
        if isinstance(color, str):
            hex_color = color
        elif color and (isinstance(color, list) or isinstance(color, tuple)):
            r = int(max(0.0, min(1.0, color[0])) * 255)
            g = int(max(0.0, min(1.0, color[1])) * 255)
            b = int(max(0.0, min(1.0, color[2])) * 255)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            self.base.qt_win.show_sub_banner(text, hex_color, duration, font_size_mult, pos_y_ratio)


    def clear_action_buttons(self):
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            self.base.qt_win.actions_overlay.dismiss()
        self._clear_dodge_overlays()

    def build_action_buttons(self, player_robot, on_click_fn):
        pass


    def build_minigame_dodge(self, on_dodge_fn, attack_dir):
        self.dodge_minigame.build(attack_dir)
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            self.base.qt_win.define_hud("warning")

    def _clear_dodge_overlays(self):
        self.dodge_minigame.clear()

    def get_active_button(self):
        return None

    def build_select_screen(self, on_select_fn):
        """No-op: seleção de personagem removida. Robô é passado via argumento CLI."""
        pass

    def show_cinematic_bars(self, show: bool):
        if self.base and hasattr(self.base, "qt_win") and self.base.qt_win:
            self.base.qt_win.show_cinematic_bars(show)
            if show:
                self.base.qt_win.define_hud("boss_intro")
            else:
                self.base.qt_win.define_hud("hud_main")
