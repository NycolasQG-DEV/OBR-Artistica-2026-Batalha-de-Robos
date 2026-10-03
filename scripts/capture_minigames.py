"""Capture the game's Qt minigame overlays without camera or robot hardware.

Run from repository root with: python scripts/capture_minigames.py
The resulting PNGs are UI previews, not captures of a live match.
"""

import os
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
sys.path.insert(0, str(GAME))
sys.path = [entry for entry in sys.path if entry and Path(entry).resolve() != ROOT]
os.chdir(GAME)

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

import engine  # Resolve the game engine before project imports adjust sys.path.
from game.minigames import get_minigame_for_attack
from ui.hud.attack_overlay import AttackMinigameOverlay
from ui.hud.dodge_overlay import DodgeMinigameOverlay
from ui.hud.instruction_overlay import MinigameInstructionOverlay

SIZE = (1920, 1080)
OUTPUT = ROOT / "docs" / "screenshots" / "minigames"


def save_overlay(overlay, filename):
    overlay.resize(*SIZE)
    overlay.show()
    QApplication.processEvents()
    image = QImage(*SIZE, QImage.Format_ARGB32)
    image.fill(QColor(9, 15, 28))
    painter = QPainter(image)
    overlay.render(painter, QPoint(0, 0))
    painter.end()
    path = OUTPUT / filename
    if not image.save(str(path)):
        raise RuntimeError(f"Could not save {path}")
    overlay.hide()
    print(f"Saved {path.relative_to(ROOT)}")


def capture_attack(champion, attack, filename):
    minigame = get_minigame_for_attack(attack, champion)
    minigame.start()
    for _ in range(24):
        minigame.update((0.56, 0.55), False, 1 / 30)
    if hasattr(minigame, "_hits"):
        minigame._hits = 7
    if hasattr(minigame, "_notes"):
        # Position notes within the visible field for a representative frame.
        minigame._notes[0]["y"] = 0.45
    if hasattr(minigame, "score"):
        # Meteor Stomp draws its gameplay in Panda3D; this is the Qt HUD.
        minigame.score = 7
    overlay = AttackMinigameOverlay()
    overlay.set_minigame(minigame)
    overlay.set_hand_pos(0.56, 0.55)
    overlay.update_minigame_state()
    save_overlay(overlay, filename)


def main():
    random.seed(2026)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    # Qt's offscreen plugin does not discover Windows fonts automatically.
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in ("arial.ttf", "arialbd.ttf", "bahnschrift.ttf", "segoeui.ttf", "seguiemj.ttf"):
        path = fonts_dir / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Arial", 12))
    for champion, attack, filename in (
        ("DinoByte", "atk0", "mordida-jurassica.png"),
        ("DinoByte", "atk2", "meteor-stomp-hud.png"),
        ("PenLinux", "atk0", "dance-night.png"),
        ("PenLinux", "atk1", "escudo-de-gelo.png"),
        ("PenLinux", "atk2", "notas-musicais.png"),
    ):
        capture_attack(champion, attack, filename)

    # Tail Quake uses a Panda3D vortex plus the actual Qt instruction overlay.
    instruction = MinigameInstructionOverlay()
    instruction.lbl_instruction.setText(
        "SUCÇÃO JURÁSSICA!\nVIRE A CABEÇA PARA SUGAR ORBES!"
    )
    save_overlay(instruction, "succao-jurassica-instrucao.png")

    # The battle currently selects variant 0 (left/right dodge).
    battle = SimpleNamespace(
        dodge_variant=0,
        minigame_attack_dir="left",
        minigame_start_time=time.time() - 0.7,
        last_known_face_x=0.82,
        last_known_face_y=0.55,
        dodge_safe_time=0.3,
    )
    dodge = DodgeMinigameOverlay()
    dodge.main_win = SimpleNamespace(panda_app=SimpleNamespace(battle=battle))
    save_overlay(dodge, "desvio.png")
    app.quit()


if __name__ == "__main__":
    main()
