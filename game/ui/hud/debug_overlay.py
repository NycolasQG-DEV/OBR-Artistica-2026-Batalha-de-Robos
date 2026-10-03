# ui/hud/debug_overlay.py — Tela de debug (Ctrl+D / F12): ângulo relativo dos robôs
"""
Overlay de debug com o ângulo de rotação de cada robô.

O ângulo mostrado é RELATIVO ("tarado"), como uma balança que se zera:
no início da luta (e sempre que os robôs voltam a ficar de frente um
para o outro) o ângulo de ambos é definido como 0°. A partir daí, o
valor exibido é só o quanto o robô girou desde aquele instante — para
a esquerda (valores negativos) ou para a direita (valores positivos) —
independente do offset visual de 180° do modelo do PenLinux, que já é
compensado internamente antes de chegar aqui.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout

from ui.hud.design_system import FONT_HUD, FONT_MONO, COLOR_CYAN, COLOR_ORANGE, COLOR_GREEN, GLASS_DARK


class DebugOverlay(QFrame):
    """Painel fixo no canto superior esquerdo com o ângulo tarado dos robôs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(300, 132)

        self.setStyleSheet(f"""
            DebugOverlay {{
                background-color: {GLASS_DARK};
                border: 1.5px solid {COLOR_GREEN};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        title = QLabel("DEBUG — ÂNGULO RELATIVO (tarado)", self)
        title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-weight: 700;
            font-size: 11px;
            color: {COLOR_GREEN};
            border: none;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(title)

        def _make_row(name_default, color):
            row = QHBoxLayout()
            lbl_name = QLabel(name_default, self)
            lbl_name.setStyleSheet(f"""
                font-family: {FONT_MONO};
                font-size: 13px;
                font-weight: bold;
                color: {color};
                border: none;
                background: transparent;
            """)
            lbl_val = QLabel("+0.0°", self)
            lbl_val.setAlignment(Qt.AlignRight)
            lbl_val.setStyleSheet(f"""
                font-family: {FONT_MONO};
                font-size: 15px;
                font-weight: bold;
                color: #ffffff;
                border: none;
                background: transparent;
            """)
            row.addWidget(lbl_name)
            row.addStretch(1)
            row.addWidget(lbl_val)
            layout.addLayout(row)
            return lbl_name, lbl_val

        self.lbl_player_name, self.lbl_player_val = _make_row("PLAYER", COLOR_CYAN)
        self.lbl_boss_name, self.lbl_boss_val = _make_row("BOSS", COLOR_ORANGE)

        hint = QLabel("Ctrl+D / F12 para ocultar", self)
        hint.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 10px;
            color: rgba(255, 255, 255, 0.45);
            border: none;
            background: transparent;
        """)
        layout.addWidget(hint)

    def set_values(self, player_name, player_angle, boss_name, boss_angle):
        self.lbl_player_name.setText(player_name)
        self.lbl_boss_name.setText(boss_name)
        self.lbl_player_val.setText(f"{player_angle:+.1f}°")
        self.lbl_boss_val.setText(f"{boss_angle:+.1f}°")
