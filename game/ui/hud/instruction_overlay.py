# ui/hud/instruction_overlay.py — overlay de instrução para os minigames
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from ui.hud.design_system import FONT_HUD

class MinigameInstructionOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._scale = 1.0

        # Background frame for styling and fading
        self.bg_frame = QFrame(self)
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(2, 6, 14, 0.55);
                border: none;
            }
        """)

        # Main layout of outer widget holds only the bg_frame
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.bg_frame)

        # Layout inside the bg_frame holds all the actual UI elements
        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.addStretch()

        self.lbl_instruction = QLabel("[!] Mova-se para desviar corretamente!", self.bg_frame)
        self.lbl_instruction.setAlignment(Qt.AlignCenter)
        self.lbl_instruction.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 34px;
            font-weight: 850;
            color: white;
            background: transparent;
            border: none;
            letter-spacing: 1.5px;
            line-height: 48px;
        """)
        bg_layout.addWidget(self.lbl_instruction)
        bg_layout.addStretch()

    def scale_ui(self, scale):
        self._scale = scale
        inst_font_size = int(34 * scale)
        inst_line_height = int(48 * scale)
        inst_spacing = 1.5 * scale
        self.lbl_instruction.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: {inst_font_size}px;
            font-weight: 850;
            color: white;
            background: transparent;
            border: none;
            letter-spacing: {inst_spacing}px;
            line-height: {inst_line_height}px;
        """)
