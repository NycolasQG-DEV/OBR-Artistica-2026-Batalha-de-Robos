# ui/hud/actions_hud_effects.py — efeitos e animações visuais do jackpot (celebration, shake, flashes)
from PySide6.QtCore import QTimer

class ActionsHUDEffectsMixin:
    def _trigger_selection_celebration(self, target_name):
        self.lbl_status.setText(f"🎉 SELECIONADO: {target_name}! 🎉")
        self.lbl_status.setStyleSheet("font-family: Bahnschrift; font-size: 24px; font-weight: 900; color: #00ffaa;")

        # Shake casing strongly
        self.shake_intensity = 1.2
        self.shake_timer.start()

        # Neon flash border color changes
        self.flash_counter = 0
        self.flash_timer.start()

        # Advance with a delay
        QTimer.singleShot(2000, self._finalize_selection)

    def _on_shake_tick(self):
        self.shake_intensity -= 0.08
        if self.shake_intensity <= 0.0:
            self.shake_intensity = 0.0
            self.shake_timer.stop()
        self._reposition_panel()

    def _on_flash_tick(self):
        self.flash_counter += 1
        colors = ["#ffcc00", "#00ffaa", "#00ecff", "#ff00ff"]
        color = colors[self.flash_counter % len(colors)]
        self.jackpot_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(6, 10, 22, 0.96);
                border: 5px solid {color};
                border-radius: 28px;
            }}
        """)
        if self.flash_counter >= 15:
            self.flash_timer.stop()
            self.jackpot_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(6, 10, 22, 0.96);
                    border: 4px solid #ffaa00;
                    border-radius: 28px;
                }}
            """)
