from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from engine.base_screen import BaseScreen
from ui.hud import RobotCard, FONT_HUD, COLOR_YELLOW
from settings import ROBOT_OPTIONS
from ui.hud.hud_scaling import compute_ui_scale
from ui.hud.lever_canvas import LeverCanvas
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QPixmap, QPainter
from ui.hud.svg_icons import SVG_HAND_OPEN



class CharacterSelectScreen(QWidget, BaseScreen):
    robot_chosen = Signal(str)

    def __init__(self, main_win, parent=None):
        QWidget.__init__(self, parent)
        BaseScreen.__init__(self)
        self.main_win = main_win
        self.setObjectName("SelectScreen")
        self.setStyleSheet(f"""
            #SelectScreen {{
                background: transparent;
            }}
        """)
        
        self.bg_pixmap = QPixmap("assets/textures/background_choose.png")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(36)

        # Title container
        self.title_layout = QVBoxLayout()
        self.title_layout.setSpacing(6)

        self.lbl_title_img = QLabel(self)
        self.lbl_title_img.setAlignment(Qt.AlignCenter)
        self.lbl_title_img.setStyleSheet("background: transparent; border: none;")
        self.title_pixmap = QPixmap("assets/textures/title_choose.png")
        self.lbl_title_img.setPixmap(self.title_pixmap.scaledToWidth(800, Qt.SmoothTransformation))
        self.title_layout.addWidget(self.lbl_title_img)
        main_layout.addLayout(self.title_layout)

        # Cards container
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(28)
        self.cards_layout.setAlignment(Qt.AlignCenter)

        # Build cards from settings.py ROBOT_OPTIONS
        self.cards = []
        icons = {"PenLinux": "*", "DinoByte": "*"}
        
        # We need self.card_pen and self.card_dino properties specifically because main.py updates their hover state on CV input!
        self.card_pen = None
        self.card_cow = None  # Leave as None/dummy to avoid any key errors
        self.card_dino = None

        for opt in ROBOT_OPTIONS:
            name = opt["name"]
            if name == "DinoByte":
                continue
            color = opt["color"]
            desc = opt["desc"]
            icon = icons.get(name, "*")
            
            # Convert color tuple to hex string
            r, g, b, a = color
            color_hex = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            card = RobotCard(name, icon, desc, color_hex, self)
            card.selected.connect(self.robot_chosen)
            self.cards_layout.addWidget(card)
            self.cards.append(card)
            
            if name == "PenLinux":
                self.card_pen = card

        main_layout.addLayout(self.cards_layout)
        self.scale_ui(1.0)

    def on_enter(self):
        # Notify GameWindow
        if self.main_win:
            self.show()
            self.main_win.define_hud("select_robot")
            if self.main_win.panda_app:
                self.main_win.panda_app.cam_ctrl.enter_select_mode()
                from settings import C_YELLOW
                self.main_win.panda_app.hud.show_banner("ESCOLHA SEU CAMPEÃO!", C_YELLOW)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        scale = compute_ui_scale(self.width(), self.height())
        self.scale_ui(scale)

    def scale_ui(self, scale):
        self.layout().setContentsMargins(int(40 * scale), int(40 * scale), int(40 * scale), int(40 * scale))
        self.layout().setSpacing(int(36 * scale))

        self.title_layout.setSpacing(int(6 * scale))
        self.cards_layout.setSpacing(int(28 * scale))

        if self.title_pixmap and not self.title_pixmap.isNull():
            w = int(800 * scale)
            self.lbl_title_img.setPixmap(self.title_pixmap.scaledToWidth(w, Qt.SmoothTransformation))

        for card in self.cards:
            card.scale_ui(scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        if hasattr(self, "bg_pixmap") and not self.bg_pixmap.isNull():
            # Draw stretched to cover
            painter.drawPixmap(self.rect(), self.bg_pixmap)
        super().paintEvent(event)
