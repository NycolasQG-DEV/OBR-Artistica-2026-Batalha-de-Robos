# game/minigames/__init__.py — Minigames de ataque com visão computacional
import importlib
from game.minigames.base_minigame import BaseAttackMinigame
from game.minigames.dodge import DodgeMinigame

LAZY_MINIGAME_MAP = {
    "DinoByte": {
        "atk0": ("game.minigames.target_aim", "JurassicBiteMinigame"),
        "atk2": ("game.minigames.meteor_stomp", "MeteorStompMinigame"),
    },
    "PenLinux": {
        "atk0": ("game.minigames.dance_night", "DanceNightMinigame"),
        "atk1": ("game.minigames.frost_barrier", "FrostBarrierMinigame"),
        "atk2": ("game.minigames.symphony_wave", "SymphonyWaveMinigame"),
    }
}

def get_minigame_for_attack(attack_key: str, champion_name: str = "PenLinux") -> BaseAttackMinigame:
    """Returns a new instance of the minigame class for the given attack key (Lazy Loaded)."""
    champ_map = LAZY_MINIGAME_MAP.get(champion_name)
    if not champ_map:
        raise ValueError(f"No minigames registered for champion: {champion_name}")
        
    module_info = champ_map.get(attack_key)
    if not module_info:
        raise ValueError(f"No minigame registered for {champion_name} attack: {attack_key}")
        
    module_path, class_name = module_info
    module = importlib.import_module(module_path)
    klass = getattr(module, class_name)
    return klass()
