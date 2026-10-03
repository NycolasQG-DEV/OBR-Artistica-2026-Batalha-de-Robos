"""Smoke tests for both entry points of the champion selection flow."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_gui_smoke(code, cwd):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


class DinoByteSelectionTests(unittest.TestCase):
    def test_presentation_selection_passes_dinobyte_to_runner(self):
        run_gui_smoke(
            """
from PySide6.QtWidgets import QApplication, QWidget
from engine.config import SlideConfig
from players.selection_player import SelectionSlidePlayer

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.runner = type('Runner', (), {'selected_champion': None, 'skip_next': lambda self: None})()

app = QApplication([])
window = Window()
slide = SelectionSlidePlayer(SlideConfig({'type': 'selection'}), window)
assert not slide.btn_dinobyte.card_pixmap.isNull()
assert not slide.btn_penlinux.card_pixmap.isNull()
slide.btn_dinobyte.click()
assert slide.selected_champion == window.runner.selected_champion == 'DinoByte'
""",
            ROOT,
        )

    def test_game_selection_and_three_dinobyte_attacks(self):
        run_gui_smoke(
            """
from PySide6.QtWidgets import QApplication
from game.screens.character_select_screen import CharacterSelectScreen
from game.combat.battle_logic import BattleLogic
from game.minigames import get_minigame_for_attack
from settings import C_ORANGE

app = QApplication([])
chosen = []
screen = CharacterSelectScreen(None)
screen.robot_chosen.connect(chosen.append)
assert screen.card_dino is not None and screen.card_pen is not None
screen.card_dino.click()
assert chosen == ['DinoByte']

battle = BattleLogic(None, lambda *a: None, lambda *a: None, lambda *a: None)
battle.select_player_robot(C_ORANGE, 'DinoByte')
assert battle.player_robot.name_code == 'DinoByte'
assert battle.ia_robot.name_code == 'PenLinux'
assert [ability.name for ability in battle.player_robot.abilities] == [
    'Mordida Jurássica', 'Sucção Jurássica', 'Meteor Stomp'
]
assert not battle.player_robot.abilities[1].triggers_minigame
assert get_minigame_for_attack('atk0', 'DinoByte').__class__.__name__ == 'JurassicBiteMinigame'
assert get_minigame_for_attack('atk2', 'DinoByte').__class__.__name__ == 'MeteorStompMinigame'
""",
            ROOT / "game",
        )


if __name__ == "__main__":
    unittest.main()
