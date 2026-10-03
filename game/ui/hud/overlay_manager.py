# ui/hud/overlay_manager.py — management and positioning of all floating interface overlays
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QApplication, QLabel
from game.config.ui import BASE_DESIGN_WIDTH, BASE_DESIGN_HEIGHT
from ui.hud.hud_scaling import compute_ui_scale
from engine.ui_kit.animations import fade_in_widget, fade_overlay

class OverlayManager:
    def __init__(self, win):
        self.win = win

    def reposition_overlays(self):
        """Aligns all floating overlays relative to the viewport."""
        if not hasattr(self.win, "panda_container"):
            return

        if self.win.panda_container.isVisible():
            geom = self.win.panda_container.geometry()
            origin = self.win.panda_container.mapToGlobal(QPoint(0, 0))
        else:
            geom = self.win.geometry()
            origin = self.win.mapToGlobal(QPoint(0, 0))

        vw = geom.width()
        vh = geom.height()

        scale = compute_ui_scale(vw, vh)

        # Scale overlays first!
        self.win.boss_hp_overlay.scale_ui(scale)
        self.win.player_hud_overlay.scale_ui(scale)
        self.win.cv_cursor.scale_ui(scale)
        self.win.minigame_instruction_overlay.scale_ui(scale)
        self.win.robotic_vision_overlay.scale_ui(scale)

        # ── Boss HP bar: top center ──────────────────────────────────
        boss_w = self.win.boss_hp_overlay.width()
        boss_x = origin.x() + (vw - boss_w) // 2
        boss_y = origin.y() + int(12 * scale)
        self.win.boss_hp_overlay.move(boss_x, boss_y)

        # ── Player HUD: top-left or fullscreen minigame mode ─────────────
        if getattr(self.win.player_hud_overlay, "_jurassic_bite_active", False):
            self.win.player_hud_overlay.setFixedSize(vw, vh)
            self.win.player_hud_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
            self.win.player_hud_overlay.webcam.setFixedSize(vw, vh)
            self.win.player_hud_overlay.webcam.lbl_video.setFixedSize(vw, vh)
        else:
            self.win.player_hud_overlay.move(self.win.get_player_hud_target())

        if self.win.player_hud_overlay.isVisible():
            self.win.player_hud_overlay.raise_()

        # ── Actions HUD: fullscreen ─────────────────────────────────
        self.win.actions_overlay.setGeometry(origin.x(), origin.y(), vw, vh)

        # ── Robotic Vision HUD: fullscreen ──────────────────────────
        self.win.robotic_vision_overlay.setGeometry(origin.x(), origin.y(), vw, vh)

        # ── Dodge Minigame Overlay: fullscreen ────────────────────────
        self.win.dodge_minigame_overlay.scale_ui(scale)
        self.win.dodge_minigame_overlay.setGeometry(origin.x(), origin.y(), vw, vh)

        # ── Cinematic bars ───────────────────────────────────────────
        bar_h = int(vh * 0.18)
        if hasattr(self.win, "cinema_top"):
            if not (hasattr(self.win, "_cinema_top_anim") and self.win._cinema_top_anim.state() == QPropertyAnimation.Running):
                self.win.cinema_top.setGeometry(origin.x(), origin.y(), vw, bar_h)
        if hasattr(self.win, "cinema_bottom"):
            if not (hasattr(self.win, "_cinema_bottom_anim") and self.win._cinema_bottom_anim.state() == QPropertyAnimation.Running):
                self.win.cinema_bottom.setGeometry(origin.x(), origin.y() + vh - bar_h, vw, bar_h)

        # ── Debug overlay: canto superior esquerdo ─────────────────────
        if hasattr(self.win, "debug_overlay") and self.win.debug_overlay.isVisible():
            self.win.debug_overlay.move(origin.x() + 16, origin.y() + 16)

        # ── Banner ───────────────────────────────────────────────────
        if hasattr(self.win, "banner_overlay") and self.win.banner_overlay.isVisible():
            w = self.win.width()
            h = self.win.height()
            bw = self.win.banner_overlay.width()
            bh = self.win.banner_overlay.height()
            global_pos = self.win.mapToGlobal(QPoint((w - bw) // 2, int(h * 0.25) - bh // 2))
            self.win.banner_overlay.move(global_pos)

        # Raise overlays
        self.raise_overlays()

    def raise_overlays(self):
        """Brings all visible floating overlays back to the top of the stays-on-top stack."""
        overlays = (
            self.win.boss_hp_overlay, self.win.player_hud_overlay, self.win.actions_overlay,
            self.win.minigame_instruction_overlay, self.win.attack_minigame_overlay,
            self.win.dodge_minigame_overlay,
            self.win.robotic_vision_overlay, self.win.cinema_top, self.win.cinema_bottom,
            self.win.banner_overlay, self.win.cv_cursor, self.win.debug_overlay,
        )
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                p_hwnd = int(self.win.winId()) if hasattr(self.win, "winId") else 0
                SetWindowLongPtr = getattr(ctypes.windll.user32, "SetWindowLongPtrW", ctypes.windll.user32.SetWindowLongW)
                GWLP_HWNDPARENT = -8
                for overlay in overlays:
                    if hasattr(overlay, "isVisible") and overlay.isVisible():
                        hwnd = int(overlay.winId())
                        if p_hwnd and hwnd:
                            SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, p_hwnd)
                        overlay.raise_()
            except Exception:
                for overlay in overlays:
                    if hasattr(overlay, "isVisible") and overlay.isVisible():
                        overlay.raise_()
        else:
            for overlay in overlays:
                if hasattr(overlay, "isVisible") and overlay.isVisible():
                    overlay.raise_()

    def show_battle_overlays(self):
        """Shows boss HP and player HUD overlays. Actions shown separately."""
        self.reposition_overlays()
        fade_in_widget(self.win.boss_hp_overlay, 500)
        fade_in_widget(self.win.player_hud_overlay, 600)
        if hasattr(self.win, "player_hud_overlay"):
            self.win.player_hud_overlay.show()
            self.win.player_hud_overlay.webcam.show()
            self.win.player_hud_overlay.stats_container.show()
        if hasattr(self.win, "boss_hp_overlay"):
            self.win.boss_hp_overlay.show()

    def hide_all_overlays(self):
        """Hides all floating HUD overlays."""
        self.win.boss_hp_overlay.hide()
        self.win.player_hud_overlay.hide()
        self.win.actions_overlay.dismiss()

        # Stop any active minigame instruction overlay animations
        if hasattr(self.win, "_fade_inst_anim") and self.win._fade_inst_anim.state() == QPropertyAnimation.Running:
            self.win._fade_inst_anim.stop()
        if hasattr(self.win, "_fade_inst_out") and self.win._fade_inst_out.state() == QPropertyAnimation.Running:
            self.win._fade_inst_out.stop()
        if hasattr(self.win, "_fade_inst_exit") and self.win._fade_inst_exit.state() == QPropertyAnimation.Running:
            self.win._fade_inst_exit.stop()

        self.win.minigame_instruction_overlay.hide()
        self.win.minigame_instruction_overlay.setWindowOpacity(1.0)
        self.win.attack_minigame_overlay.stop_painting()
        self.win.player_hud_overlay.show_stats()
        self.win._hovered_widget = None
        self.win._hover_start_time = None
        self.win.cv_cursor.set_cursor_state(None, None, 0.0, False)
        if hasattr(self.win, "robotic_vision_overlay"):
            self.win.robotic_vision_overlay.stop_effect()

    def hide_all_overlays_temporarily(self):
        self.win.boss_hp_overlay.hide()
        self.win.player_hud_overlay.hide()
        self.win.actions_overlay.hide()
        self.win.minigame_instruction_overlay.hide()
        if hasattr(self.win, "robotic_vision_overlay"):
            self.win.robotic_vision_overlay.stop_effect()
        if hasattr(self.win, "cinema_top"):
            self.win.cinema_top.hide()
        if hasattr(self.win, "cinema_bottom"):
            self.win.cinema_bottom.hide()
        if hasattr(self.win, "banner_overlay"):
            self.win.banner_overlay.hide()

    def restore_all_overlays_after_minimize(self):
        if not self.win.panda_app:
            return
        state = self.win.panda_app.battle.state
        if state == "select_robot":
            self.hide_all_overlays()
        else:
            QTimer.singleShot(0, self.reposition_overlays)
            self.show_battle_overlays()
            if state == "player_turn":
                self.win.actions_overlay.show()
                self.win.actions_overlay.raise_()
                self.win.actions_overlay.activateWindow()
                self.win.player_hud_overlay.raise_()
            elif state == "minigame" and getattr(self.win.player_hud_overlay, "_minigame_intro_active", False):
                self.win.minigame_instruction_overlay.show()
                self.win.minigame_instruction_overlay.raise_()

    def update_game_state(self, state_data):
        """Updates HP bars, names, and countdown timer in overlays."""
        # Boss HP bar
        boss_hp = state_data.get("boss_hp", 100)
        boss_name = state_data.get("boss_name", "BOSS")
        boss_status = state_data.get("boss_status", "")
        self.win.boss_hp_overlay.lbl_b_name.setText(f"{boss_name}")
        self.win.boss_hp_overlay.lbl_b_hp_val.setText(f"{boss_hp} / 100")
        self.win.boss_hp_overlay.b_hp_bar.setValue(int(boss_hp))
        self.win.boss_hp_overlay.lbl_b_status.setText(boss_status)

        # Match countdown timer
        match_time = state_data.get("match_time_remaining", 90.0)
        minutes = int(match_time) // 60
        seconds = int(match_time) % 60
        if hasattr(self.win.boss_hp_overlay, "lbl_match_timer"):
            self.win.boss_hp_overlay.lbl_match_timer.setText(f"{minutes:02d}:{seconds:02d}")

        # Player HP bar
        player_hp = state_data.get("player_hp", 100)
        player_name = state_data.get("player_name", "PLAYER")
        player_status = state_data.get("player_status", "")
        self.win.player_hud_overlay.lbl_p_name.setText(f"{player_name}")
        self.win.player_hud_overlay.lbl_p_hp_val.setText(f"{player_hp} / 100")
        self.win.player_hud_overlay.p_hp_bar.setValue(int(player_hp))
        self.win.player_hud_overlay.lbl_p_status.setText(player_status)

    def show_banner(self, text, color_hex="#ffcc00", duration=2.0, font_size_mult=1.0, pos_y_ratio=0.25):
        """Shows a neon glowing warning/intro banner in the screen center."""
        if not text:
            if hasattr(self.win, "banner_overlay"):
                self.win.banner_overlay.hide()
            return

        vw = self.win.panda_container.width()
        vh = self.win.panda_container.height()
        scale = compute_ui_scale(vw, vh)

        self.win.banner_overlay.setText(text)
        font_size = int(26 * font_size_mult * scale)
        border_width = max(1, int(2 * scale))
        radius = int(8 * scale)
        padding_y = int(12 * scale)
        padding_x = int(36 * scale)
        self.win.banner_overlay.setStyleSheet(f"""
            font-family: Bahnschrift, 'Segoe UI Semibold', sans-serif;
            font-size: {font_size}px;
            font-weight: 900;
            color: {color_hex};
            background-color: rgba(4, 7, 13, 0.9);
            border: {border_width}px solid {color_hex};
            border-radius: {radius}px;
            padding: {padding_y}px {padding_x}px;
        """)
        self.win.banner_overlay.adjustSize()

        w = self.win.width()
        h = self.win.height()
        bw = self.win.banner_overlay.width()
        bh = self.win.banner_overlay.height()
        global_pos = self.win.mapToGlobal(QPoint((w - bw) // 2, int(h * pos_y_ratio) - bh // 2))

        self.win.banner_overlay.move(global_pos)
        self.win.banner_overlay.show()
        self.win.banner_overlay.raise_()

        QTimer.singleShot(int(duration * 1000), self.win.banner_overlay.hide)

    def show_sub_banner(self, text, color_hex="#ffffff", duration=2.0, font_size_mult=1.0, pos_y_ratio=0.18):
        """Shows an secondary text banner simultaneously above the main banner."""
        if not hasattr(self.win, "banner_sub_overlay"):
            from PySide6.QtWidgets import QLabel
            self.win.banner_sub_overlay = QLabel(self.win)
            self.win.banner_sub_overlay.main_win = self.win
            self.win.banner_sub_overlay.setAlignment(Qt.AlignCenter)
            self.win.banner_sub_overlay.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
            self.win.banner_sub_overlay.setAttribute(Qt.WA_TranslucentBackground)

        if not text:
            self.win.banner_sub_overlay.hide()
            return

        vw = self.win.panda_container.width()
        vh = self.win.panda_container.height()
        scale = compute_ui_scale(vw, vh)

        self.win.banner_sub_overlay.setText(text)
        font_size = int(24 * font_size_mult * scale)
        border_width = max(1, int(2 * scale))
        radius = int(8 * scale)
        padding_y = int(8 * scale)
        padding_x = int(24 * scale)
        self.win.banner_sub_overlay.setStyleSheet(f"""
            font-family: Bahnschrift, 'Segoe UI Semibold', sans-serif;
            font-size: {font_size}px;
            font-weight: 900;
            color: {color_hex};
            background-color: rgba(4, 7, 13, 0.85);
            border: {border_width}px solid {color_hex};
            border-radius: {radius}px;
            padding: {padding_y}px {padding_x}px;
        """)
        self.win.banner_sub_overlay.adjustSize()

        w = self.win.width()
        h = self.win.height()
        bw = self.win.banner_sub_overlay.width()
        bh = self.win.banner_sub_overlay.height()
        global_pos = self.win.mapToGlobal(QPoint((w - bw) // 2, int(h * pos_y_ratio) - bh // 2))

        self.win.banner_sub_overlay.move(global_pos)
        self.win.banner_sub_overlay.show()
        self.win.banner_sub_overlay.raise_()

        QTimer.singleShot(int(duration * 1000), self.win.banner_sub_overlay.hide)

    def show_cinematic_bars(self, show: bool):
        """Displays cinematic top/bottom bars during intro animations."""


        if hasattr(self.win, "_cinema_top_anim") and self.win._cinema_top_anim.state() == QPropertyAnimation.Running:
            self.win._cinema_top_anim.stop()
        if hasattr(self.win, "_cinema_bottom_anim") and self.win._cinema_bottom_anim.state() == QPropertyAnimation.Running:
            self.win._cinema_bottom_anim.stop()

        geom = self.win.panda_container.geometry() if self.win.panda_container.isVisible() else self.win.geometry()
        origin = self.win.panda_container.mapToGlobal(QPoint(0, 0)) if self.win.panda_container.isVisible() else self.win.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()
        bar_h = int(vh * 0.18)

        if show:
            # Esconder TODOS os elementos de HUD durante a cutscene
            self.win.player_hud_overlay.hide()
            self.win.boss_hp_overlay.hide()
            self.win.actions_overlay.hide()
            self.win.cv_cursor.hide()
            self.win.cv_cursor.set_cursor_state(None, None, 0.0, False)
            if hasattr(self.win, 'robotic_vision_overlay'):
                self.win.robotic_vision_overlay.stop_effect()
            # Esconder webcam
            self.win.player_hud_overlay.webcam.hide()


            self.win.cinema_top.setGeometry(origin.x(), origin.y() - bar_h, vw, bar_h)
            self.win.cinema_bottom.setGeometry(origin.x(), origin.y() + vh, vw, bar_h)
            
            self.win.cinema_top.show()
            self.win.cinema_bottom.show()
            self.win.cinema_top.raise_()
            self.win.cinema_bottom.raise_()

            self.win._cinema_top_anim = QPropertyAnimation(self.win.cinema_top, b"geometry")
            self.win._cinema_top_anim.setDuration(500)
            self.win._cinema_top_anim.setStartValue(QRect(origin.x(), origin.y() - bar_h, vw, bar_h))
            self.win._cinema_top_anim.setEndValue(QRect(origin.x(), origin.y(), vw, bar_h))
            self.win._cinema_top_anim.setEasingCurve(QEasingCurve.OutCubic)

            self.win._cinema_bottom_anim = QPropertyAnimation(self.win.cinema_bottom, b"geometry")
            self.win._cinema_bottom_anim.setDuration(500)
            self.win._cinema_bottom_anim.setStartValue(QRect(origin.x(), origin.y() + vh, vw, bar_h))
            self.win._cinema_bottom_anim.setEndValue(QRect(origin.x(), origin.y() + vh - bar_h, vw, bar_h))
            self.win._cinema_bottom_anim.setEasingCurve(QEasingCurve.OutCubic)

            self.win._cinema_top_anim.start()
            self.win._cinema_bottom_anim.start()
        else:
            self.win._cinema_top_anim = QPropertyAnimation(self.win.cinema_top, b"geometry")
            self.win._cinema_top_anim.setDuration(600)
            self.win._cinema_top_anim.setStartValue(self.win.cinema_top.geometry())
            self.win._cinema_top_anim.setEndValue(QRect(origin.x(), origin.y() - bar_h, vw, bar_h))
            self.win._cinema_top_anim.setEasingCurve(QEasingCurve.InOutQuad)

            self.win._cinema_bottom_anim = QPropertyAnimation(self.win.cinema_bottom, b"geometry")
            self.win._cinema_bottom_anim.setDuration(600)
            self.win._cinema_bottom_anim.setStartValue(self.win.cinema_bottom.geometry())
            self.win._cinema_bottom_anim.setEndValue(QRect(origin.x(), origin.y() + vh, vw, bar_h))
            self.win._cinema_bottom_anim.setEasingCurve(QEasingCurve.InOutQuad)

            def on_complete():
                self.win.cinema_top.hide()
                self.win.cinema_bottom.hide()
                self.show_battle_overlays()

            self.win._cinema_top_anim.finished.connect(on_complete)
            self.win._cinema_top_anim.start()
            self.win._cinema_bottom_anim.start()

    def show_robotic_vision(self, show: bool):
        """Shows or hides CRT robotic vision overlay."""
        if not hasattr(self.win, "robotic_vision_overlay"):
            return
        if show:
            self.reposition_overlays()
            self.win.robotic_vision_overlay.start_effect()
        else:
            self.win.robotic_vision_overlay.stop_effect()
