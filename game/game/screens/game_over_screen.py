from engine.base_screen import BaseScreen
from settings import C_YELLOW, C_RED, C_GRAY

class GameOverScreen(BaseScreen):
    def __init__(self, app_instance):
        self.app_instance = app_instance

    def on_enter(self):
        # Ensure we stay on the gameplay container widget
        if self.app_instance.qt_win:
            pass
            self.app_instance.hud.clear_action_buttons()
            
            winner = self.app_instance.battle.winner
            if winner == "player":
                self.app_instance.hud.show_banner("** VOCE VENCEU! **", C_YELLOW)
            elif winner == "ia":
                self.app_instance.hud.show_banner("DERROTA...", C_RED)
            else:
                self.app_instance.hud.show_banner("EMPATE!", C_GRAY)
                
            self.app_instance.cam_ctrl.cinematic_game_over()
