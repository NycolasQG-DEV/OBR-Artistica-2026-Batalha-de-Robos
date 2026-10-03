# game/config/battle.py — constantes de batalha e turnos
from game.config.colors import C_CYAN, C_ORANGE

# ── Batalha ───────────────────────────────────────────────────────────
MAX_HP               = 100
DEFENSE_REDUCTION    = 0.45
MAX_ROUNDS           = 5

# ── FPS ───────────────────────────────────────────────────────────────
FPS = 60

# ── Turnos ────────────────────────────────────────────────────────────
PLAYER_TURN_TIMEOUT = 10.0
MATCH_DURATION      = 90.0   # Tempo limite da partida em segundos (1 minuto e meio)
SELECTION_HOLD_TIME = 0.8
IA_THINK_TIME       = 1.2
MINIGAME_DURATION   = 3.0  # Janela de desvio de 3 segundos
ATTACK_MINIGAME_INSTRUCTION_TIME = 1.5  # Tempo da tela de instrução do minigame de ataque

# ── Screen shake ─────────────────────────────────────────────────────
SHAKE_LIGHT  = 0.08
SHAKE_MEDIUM = 0.18
SHAKE_HEAVY  = 0.32

# ── Robôs disponíveis ─────────────────────────────────────────────────
ROBOT_OPTIONS = [
    {"name": "PenLinux",    "color": C_CYAN,   "desc": "Gelo"},
    {"name": "DinoByte",    "color": C_ORANGE, "desc": "Fogo"},
]


