# ui/hud/hud_mode_transitions.py — HUD mode transitions and minigame display
import time
from PySide6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation
from PySide6.QtWidgets import QApplication
from ui.hud.hud_scaling import compute_ui_scale
from engine.ui_kit.animations import fade_in_widget, fade_overlay, slide_fade_in_boss_bar

class HUDModeTransitions:
    def __init__(self, win):
        self.win = win

    def define_hud(self, hud_name, transition=0.5):
        """Switches UI stacked page and configures overlay visibility."""
        if hud_name == "select_robot":
            self.win.stacked_widget.setCurrentIndex(0)
            self.win.overlay_manager.hide_all_overlays()
            self.win.player_hud_overlay.hide_stats()
            fade_in_widget(self.win.player_hud_overlay, 600)
            self.set_webcam_mode("normal")
            if self.win.panda_app:
                self.win.panda_app._webcam_mode = "normal"
        
        elif hud_name in ("hud_main", "warning", "boss_intro"):
            self.win.stacked_widget.setCurrentIndex(1)
            QApplication.processEvents()

            if hud_name == "hud_main":
                self.win.overlay_manager.show_battle_overlays()
                self.set_webcam_mode("normal")
                if self.win.panda_app:
                    self.win.panda_app._webcam_mode = "normal"
            elif hud_name == "warning":
                self.set_webcam_mode("maximized")
                if self.win.panda_app:
                    self.win.panda_app._webcam_mode = "maximized"
            else:
                self.win.overlay_manager.hide_all_overlays()
                self.win.cv_cursor.hide()
                self.win.cv_cursor.set_cursor_state(None, None, 0.0, False)
                self.win.actions_overlay.hide()
                self.set_webcam_mode("hidden")
                if self.win.panda_app:
                    self.win.panda_app._webcam_mode = "hidden"

    def animate_player_hud(self, to_selection: bool):
        """Maintains PlayerHUDOverlay consistently at top-left with stats visible."""
        self.win.player_hud_overlay.show_stats()
        target_pos = self.win.get_player_hud_target()
        self.win.player_hud_overlay.move(target_pos)

    def set_webcam_mode(self, mode):
        """Controls webcam panel visibility and size."""
        if mode == "hidden":
            self.win.player_hud_overlay.webcam.hide()
        elif mode == "fullscreen":
            geom = self.win.panda_container.geometry()
            origin = self.win.panda_container.mapToGlobal(self.win.QPoint(0, 0)) if hasattr(self.win, 'QPoint') else self.win.panda_container.mapToGlobal(self.win.geometry().topLeft() * 0) # hacky
            # actually we can just import QPoint
            from PySide6.QtCore import QPoint
            origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
            vw = geom.width()
            vh = geom.height()
            
            self.win.player_hud_overlay.stats_container.hide()
            self.win.player_hud_overlay.setStyleSheet("PlayerHUDOverlay { background-color: transparent; border: none; border-radius: 0px; }")
            self.win.player_hud_overlay.layout().setContentsMargins(0, 0, 0, 0)
            self.win.player_hud_overlay.webcam.setStyleSheet("WebcamWidget { background: transparent; border: none; border-radius: 0px; }")
            
            QMAX = 16777215
            self.win.player_hud_overlay.setMinimumSize(0, 0)
            self.win.player_hud_overlay.setMaximumSize(QMAX, QMAX)
            self.win.player_hud_overlay.webcam.setMinimumSize(0, 0)
            self.win.player_hud_overlay.webcam.setMaximumSize(QMAX, QMAX)
            self.win.player_hud_overlay.webcam.lbl_video.setMinimumSize(0, 0)
            self.win.player_hud_overlay.webcam.lbl_video.setMaximumSize(QMAX, QMAX)
            
            self.win.player_hud_overlay.setFixedSize(vw, vh)
            self.win.player_hud_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
            self.win.player_hud_overlay.webcam.setFixedSize(vw, vh)
            self.win.player_hud_overlay.webcam.lbl_video.setFixedSize(vw, vh)
            
            self.win.player_hud_overlay.setWindowOpacity(0.35)
            self.win.player_hud_overlay.show()
            self.win.player_hud_overlay.webcam.show()
            self.win.player_hud_overlay.raise_()
        else:
            geom = self.win.panda_container.geometry()
            from ui.hud.hud_scaling import compute_ui_scale
            scale = compute_ui_scale(geom.width(), geom.height())
            self.win.player_hud_overlay.stats_container.show()
            self.win.player_hud_overlay.setStyleSheet(f"PlayerHUDOverlay {{ background-color: rgba(6, 12, 24, 0.75); border: none; border-radius: {int(14 * scale)}px; }}")
            self.win.player_hud_overlay.layout().setContentsMargins(int(14*scale), int(14*scale), int(14*scale), int(14*scale))
            self.win.player_hud_overlay.setWindowOpacity(1.0)
            self.win.player_hud_overlay.scale_ui(scale)
            self.win.player_hud_overlay.move(self.win.get_player_hud_target())
            self.win.player_hud_overlay.show()
            self.win.player_hud_overlay.webcam.show()

    def enter_selection_hud_mode(self):
        """Enters player action selection turn: keeps webcam and player HUD in default top-left position."""
        geom = self.win.panda_container.geometry()
        origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()
        scale = compute_ui_scale(vw, vh)

        # Keeps normal size
        self.set_webcam_mode("normal")
        self.win.player_hud_overlay.move(self.win.get_player_hud_target())
        
        self.win.player_hud_overlay.show()
        self.win.player_hud_overlay.webcam.show()
        self.win.boss_hp_overlay.show()

        # Exibe o overlay de seleção de ação centralizado
        self.win.actions_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
        self.win.actions_overlay.scale_ui(scale)
        self.win.actions_overlay.reveal_jackpot()
        self.win.actions_overlay.raise_()
        self.win.actions_overlay.activateWindow()


    def exit_selection_hud_mode(self):
        """Exits player action selection turn: restores webcam to top-left and reveals HP bars."""
        geom = self.win.panda_container.geometry()
        vw = geom.width()
        vh = geom.height()
        scale = compute_ui_scale(vw, vh)

        self.win.player_hud_overlay.stats_container.show()
        self.win.player_hud_overlay.setStyleSheet(f"""
            PlayerHUDOverlay {{
                background-color: rgba(6, 12, 24, 0.75);
                border: none;
                border-radius: {int(14 * scale)}px;
            }}
        """)
        self.win.player_hud_overlay.layout().setContentsMargins(
            int(14 * scale), int(14 * scale), int(14 * scale), int(14 * scale)
        )
        
        # Remove opacity effect from webcam
        self.win.player_hud_overlay.setWindowOpacity(1.0)
        self.win.player_hud_overlay.webcam.setGraphicsEffect(None)
        
        # Restore size logic by calling scale_ui which resets fixed size
        self.win.player_hud_overlay.scale_ui(scale)
        self.win.player_hud_overlay.move(self.win.get_player_hud_target())
        
        self.win.boss_hp_overlay.show()
        slide_fade_in_boss_bar(self.win.boss_hp_overlay, 600)

    def enter_minigame_hud_mode(self, attack_dir):
        """Hides all HUD overlays and expands player HUD (webcam) to fullscreen for minigame."""
        if hasattr(self.win, "cinema_top"):
            self.win.cinema_top.hide()
        if hasattr(self.win, "cinema_bottom"):
            self.win.cinema_bottom.hide()

        self.win.actions_overlay.dismiss()
        self.win.cv_cursor.hide()
        self.win.cv_cursor.set_cursor_state(None, None, 0.0, False)
        QApplication.setOverrideCursor(Qt.BlankCursor)

        geom = self.win.panda_container.geometry()
        origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()

        scale = compute_ui_scale(vw, vh)
        self.win._minigame_original_scale = scale

        self.win.player_hud_overlay.hide()

        boss_name = "O ROBÔ"
        if self.win.panda_app and hasattr(self.win.panda_app, "battle"):
            ia = getattr(self.win.panda_app.battle, "ia_robot", None)
            if ia:
                boss_name = getattr(ia, "name", getattr(ia, "name_code", "O ROBÔ")).upper()

        if attack_dir == "LEFT":
            inst_text = f"[!] {boss_name} AVANÇA PELA ESQUERDA! [!]\nDESVIE PARA A DIREITA (RIGHT)"
        elif attack_dir == "RIGHT":
            inst_text = f"[!] {boss_name} AVANÇA PELA DIREITA! [!]\nDESVIE PARA A ESQUERDA (LEFT)"
        elif attack_dir == "SWEEP":
            if random.random() < 0.5:
                inst_text = "[!] VARREDURA ALTA! [!]\nABAIXE-SE PARA DESVIAR (DUCK)"
            else:
                inst_text = "[!] VARREDURA BAIXA! [!]\nINCLINE-SE / LEVANTE-SE PARA DESVIAR"
        else:
            inst_text = "[!] GRID DO CAOS! [!]\nMOVA A CABEÇA PARA O QUADRANTE VERDE"

        if self.win.panda_app and hasattr(self.win.panda_app, "battle"):
            self.win.panda_app.battle.minigame_start_time = time.time()

        # Toca som de explicação (dodge) com Audio Ducking na BGM
        if self.win.panda_app and hasattr(self.win.panda_app, "loader"):
            try:
                snd = self.win.panda_app.loader.loadSfx(f"assets/sounds/dodge/dodge_{attack_dir}.wav")
                if snd:
                    if hasattr(self.win.panda_app, "duck_bgm_for_sound"):
                        self.win.panda_app.duck_bgm_for_sound(snd)
                    else:
                        snd.setVolume(1.0)
                        snd.play()
            except Exception as e:
                pass

        # Configura e exibe imediatamente o overlay de minijogo de esquiva
        self.win.dodge_minigame_overlay.scale_ui(scale)
        self.win.dodge_minigame_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
        self.win.dodge_minigame_overlay.show()
        self.win.dodge_minigame_overlay.raise_()
        self.win.dodge_minigame_overlay.start_painting()

        if self.win.panda_app:
            if hasattr(self.win.panda_app, "hud"):
                self.win.panda_app.hud._dodge_safe_time = 0.0

    def exit_minigame_hud_mode(self):
        """Restores player HUD back to its normal position, size, and style."""
        QApplication.restoreOverrideCursor()
        self.win.dodge_minigame_overlay.stop_painting()
        self.win.dodge_minigame_overlay.hide()
        self.win.attack_minigame_overlay.stop_painting()
        self.win.attack_minigame_overlay.hide()
        self.win.minigame_instruction_overlay.hide()

        if not self.win.panda_app:
            return

        geom = self.win.panda_container.geometry()
        origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()

        scale = compute_ui_scale(vw, vh)

        self.win.minigame_instruction_overlay.hide()
        self.win.minigame_instruction_overlay.setWindowOpacity(1.0)

        self.win.player_hud_overlay.stats_container.show()
        self.win.player_hud_overlay.layout().setContentsMargins(
            int(14 * scale), int(14 * scale), int(14 * scale), int(14 * scale)
        )
        self.win.player_hud_overlay.scale_ui(scale)
        self.win.player_hud_overlay.move(self.win.get_player_hud_target("normal"))
        self.win.player_hud_overlay.show()

        slide_fade_in_boss_bar(self.win.boss_hp_overlay, 600)

    def enter_attack_minigame_hud_mode(self, minigame):
        """Prepares and shows the attack minigame instruction overlay, then starts the minigame."""
        if hasattr(self.win, "_hud_pos_anim") and self.win._hud_pos_anim.state() == QPropertyAnimation.Running:
            self.win._hud_pos_anim.stop()
        if hasattr(self.win, "_hud_geom_anim") and self.win._hud_geom_anim.state() == QPropertyAnimation.Running:
            self.win._hud_geom_anim.stop()
        self.win._player_hud_animating = False

        # Oculta o minijogo de esquiva para garantir que nunca fiquem dois minijogos visíveis juntos
        self.win.dodge_minigame_overlay.stop_painting()
        self.win.dodge_minigame_overlay.hide()

        self.win.actions_overlay.dismiss()
        self.win.cv_cursor.hide()
        self.win.cv_cursor.set_cursor_state(None, None, 0.0, False)
        QApplication.setOverrideCursor(Qt.BlankCursor)

        geom = self.win.panda_container.geometry()
        origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()

        scale = compute_ui_scale(vw, vh)

        inst_text = getattr(minigame, "instruction_text", "PREPARE-SE PARA O ATAQUE!")
        self.win.minigame_instruction_overlay.lbl_instruction.setText(inst_text)
        self.win.minigame_instruction_overlay.scale_ui(scale)
        self.win.minigame_instruction_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
        self.win.minigame_instruction_overlay.setWindowOpacity(0.0)
        self.win.minigame_instruction_overlay.show()
        self.win.minigame_instruction_overlay.raise_()

        # Toca som de explicação (attack) com Audio Ducking na BGM
        if self.win.panda_app and hasattr(self.win.panda_app, "loader"):
            try:
                mg_name = minigame.__class__.__name__
                sound_path = getattr(minigame, "explanation_sound", f"assets/sounds/explanations/{mg_name}.wav")
                snd = self.win.panda_app.loader.loadSfx(sound_path)
                if snd:
                    if hasattr(self.win.panda_app, "duck_bgm_for_sound"):
                        self.win.panda_app.duck_bgm_for_sound(snd)
                    else:
                        snd.setVolume(1.0)
                        snd.play()
            except Exception as e:
                pass

        self.win._fade_inst_anim = fade_overlay(self.win.minigame_instruction_overlay, 0.0, 1.0, 400)

        self.win.attack_minigame_overlay.scale_ui(scale)
        self.win.attack_minigame_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
        self.win.attack_minigame_overlay.set_minigame(minigame)

        is_jurassic_bite = minigame.__class__.__name__ in ["JurassicBiteMinigame", "DanceNightMinigame", "BlizzardSlashMinigame", "SymphonyWaveMinigame"]
        if is_jurassic_bite:
            self.win.player_hud_overlay.stats_container.hide()
            self.win.player_hud_overlay.setStyleSheet(
                "PlayerHUDOverlay { background: transparent; border: none; border-radius: 0px; }"
            )
            self.win.player_hud_overlay.layout().setContentsMargins(0, 0, 0, 0)
            self.win.player_hud_overlay.webcam.setStyleSheet(
                "WebcamWidget { background-color: transparent; border: none; border-radius: 0px; }"
            )

            QMAX = 16777215
            self.win.player_hud_overlay.setMinimumSize(0, 0)
            self.win.player_hud_overlay.setMaximumSize(QMAX, QMAX)
            self.win.player_hud_overlay.webcam.setMinimumSize(0, 0)
            self.win.player_hud_overlay.webcam.setMaximumSize(QMAX, QMAX)
            self.win.player_hud_overlay.webcam.lbl_video.setMinimumSize(0, 0)
            self.win.player_hud_overlay.webcam.lbl_video.setMaximumSize(QMAX, QMAX)

            self.win.player_hud_overlay.setFixedSize(vw, vh)
            self.win.player_hud_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
            self.win.player_hud_overlay.webcam.setFixedSize(vw, vh)
            self.win.player_hud_overlay.webcam.lbl_video.setFixedSize(vw, vh)

            opacity_val = 0.35 if minigame.__class__.__name__ == "SymphonyWaveMinigame" else 0.80
            self.win.player_hud_overlay.setWindowOpacity(opacity_val)
            self.win.player_hud_overlay._jurassic_bite_active = True
        
        elif minigame.__class__.__name__ == "MeteorStompMinigame":
            self.win.player_hud_overlay.setWindowOpacity(0.80)
            self.win.player_hud_overlay._meteor_stomp_active = True

        def start_gameplay():
            def on_complete():
                self.win.minigame_instruction_overlay.hide()
                self.win.minigame_instruction_overlay.setWindowOpacity(1.0)
                
            self.win._fade_inst_out = fade_overlay(self.win.minigame_instruction_overlay, 1.0, 0.0, 300, on_finished=on_complete)

            self.win.player_hud_overlay.show()
            self.win.player_hud_overlay.webcam.show()
            self.win.player_hud_overlay.raise_()

            if is_jurassic_bite:
                self.win.overlay_manager.reposition_overlays()

            minigame.start()
            self.win.attack_minigame_overlay.show()
            self.win.attack_minigame_overlay.raise_()
            self.win.attack_minigame_overlay.start_painting()

        QTimer.singleShot(3000, start_gameplay)

    def _start_attack_minigame_gameplay(self, minigame):
        def on_complete():
            self.win.minigame_instruction_overlay.hide()
            self.win.minigame_instruction_overlay.setWindowOpacity(1.0)
            
        self.win._fade_inst_out = fade_overlay(self.win.minigame_instruction_overlay, 1.0, 0.0, 300, on_finished=on_complete)

        minigame.start()
        self.win.attack_minigame_overlay.show()
        self.win.attack_minigame_overlay.raise_()
        self.win.attack_minigame_overlay.start_painting()

    def exit_attack_minigame_hud_mode(self):
        """Closes attack minigame and restores normal HUD overlays."""
        QApplication.restoreOverrideCursor()
        self.win.attack_minigame_overlay.stop_painting()
        self.win.attack_minigame_overlay.hide()
        self.win.dodge_minigame_overlay.stop_painting()
        self.win.dodge_minigame_overlay.hide()
        self.win.minigame_instruction_overlay.hide()
        
        was_jurassic = getattr(self.win.player_hud_overlay, "_jurassic_bite_active", False)
        self.win.player_hud_overlay._jurassic_bite_active = False
        
        was_meteor = getattr(self.win.player_hud_overlay, "_meteor_stomp_active", False)
        self.win.player_hud_overlay._meteor_stomp_active = False

        if was_jurassic:
            self.win.player_hud_overlay.setWindowOpacity(1.0)
            geom = self.win.panda_container.geometry()
            vw = geom.width()
            vh = geom.height()
            scale = compute_ui_scale(vw, vh)

            self.win.player_hud_overlay.stats_container.show()
            self.win.player_hud_overlay.layout().setContentsMargins(
                int(14 * scale), int(14 * scale), int(14 * scale), int(14 * scale)
            )
            self.win.player_hud_overlay.scale_ui(scale)
            self.win.player_hud_overlay.move(self.win.get_player_hud_target("normal"))
        elif was_meteor:
            self.win.player_hud_overlay.setWindowOpacity(1.0)

        slide_fade_in_boss_bar(self.win.boss_hp_overlay, 600)
        fade_in_widget(self.win.player_hud_overlay, 600)
