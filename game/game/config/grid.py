# game/config/grid.py — constantes de grid, tiles e spawn

# ── Grid ──────────────────────────────────────────────────────────────
GRID_COLS   = 5
GRID_ROWS   = 5
TILE_SIZE   = 1.42   # tiles grandes de volta
TILE_SCALE  = 1.0    # 100% (tiles colados um no outro)
TILE_HEIGHT = 0.18   # espessura do tile

# Posições de spawn e base
PLAYER_BASE_COORDS = (2.0, 4.0)
BOSS_BASE_COORDS = (2.0, 0.0)
BOSS_SCALE = (2.3, 2.3, 2.8)

# ── Robô ──────────────────────────────────────────────────────────────
ROBOT_MOVE_SPEED = 0.012  # lerp mais lento por frame para dar peso aos robôs
ROBOT_BOX_SCALE  = (0.85, 0.85, 1.1)

# ── Movimentacao Livre ───────────────────────────────────────────────
CM_PER_WORLD_UNIT = 100.0
CM_PER_GRID_UNIT = 54.0  # 54.0 cm por grid unit (perspectiva física do robô: 5x5 tiles = 2.7m)
MOVE_SPEED_CM_S_MAX = 350.0  # cm/s na velocidade maxima (255)
TURN_SPEED_DEG_S_MAX = 360.0  # graus/s na velocidade maxima (255)
ARENA_MIN_X = 0.0
ARENA_MAX_X = 4.0
ARENA_MIN_Y = 0.0
ARENA_MAX_Y = 4.0
