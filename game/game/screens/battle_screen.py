from PySide6.QtWidgets import QWidget
from engine.base_screen import BaseScreen

class BattleScreen(QWidget, BaseScreen):
    def __init__(self, main_win, parent=None):
        QWidget.__init__(self, parent)
        BaseScreen.__init__(self)
        self.main_win = main_win
        self.setStyleSheet("background: black;")

    def on_enter(self):
        if self.main_win:
            pass
            # Não reativar HUD completa durante a cutscene de introdução
            is_intro = False
            if hasattr(self.main_win, 'panda_app') and self.main_win.panda_app:
                if hasattr(self.main_win.panda_app, 'battle') and self.main_win.panda_app.battle:
                    is_intro = self.main_win.panda_app.battle.state == "intro"
            if not is_intro:
                self.main_win.define_hud("hud_main")

