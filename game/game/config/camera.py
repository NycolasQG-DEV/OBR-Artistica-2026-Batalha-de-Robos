# game/config/camera.py — constantes de câmera

# ── Câmera isométrica ────────────────────────────────────────────────
CAM_DISTANCE  = 20.0
CAM_PITCH     = -30   # graus (câmera frontal mais focada e vertical)
CAM_HEADING   = 0     # graus (ângulo reto olhando de frente)

# ── Cinematica da câmera ─────────────────────────────────────────────
CAM_INTRO_DURATION    = 2.5   # duração da intro cinemática
CAM_SELECT_SPIN_TIME  = 1.8   # tempo do spin ao selecionar campeão
CAM_BATTLE_ZOOM_DIST  = 15.0  # distância do close-in durante batalha
CAM_SELECT_ZOOM_DIST  = 25.0  # distância afastada na tela de seleção
CAM_ORBIT_SPEED       = 14.0   # graus/s de rotação orbital suave
CAM_DANCE_ZOOM_DIST   = 9.5    # close-up zoom distance for dance night minigame

# ── Câmera POV (3ª pessoa por trás do robô atacante) ──────────────────
# Todos os valores são relativos ao centro do robô.
POV_HEAD_HEIGHT  = 1.6   # altura da câmera acima da base do robô (unidades)
POV_OFFSET_UP    = 0.5   # deslocamento extra para CIMA (unidades)
POV_OFFSET_BACK  = 2.8   # deslocamento para TRÁS do robô (unidades)
POV_PITCH        = -22.0 # ângulo vertical da câmera (olha levemente para baixo em direção ao inimigo)
POV_LERP_SPEED   = 6.0   # velocidade de transição (mais suave que first-person)

# ── Configurações do PiP (Picture-in-Picture) ───────────────────────
PIP_MIN_W = 0.54               # largura minimizada
PIP_MIN_H = 0.54               # altura minimizada
PIP_MAX_W = 1.65               # largura maximizada (focada)
PIP_MAX_H = 1.05               # altura maximizada (focada)
PIP_MARGIN = 0.03              # margem mínima com as bordas da tela

# ── Câmera POV (Tail Quake Minigame) ────────────────────────────
TAIL_POV_FORWARD = 0.45       # deslocamento para frente do centro do robô (para não ver o interior)
TAIL_POV_HEIGHT = 1.35        # altura dos olhos do robô acima do chão
TAIL_POV_PITCH = -12.0        # inclinação para baixo (para ver as orbes no chão)
TAIL_CAM_FOV = 74.0           # FOV maior para sensação de cockpit/primeira pessoa
TAIL_CAM_LERP = 7.5           # velocidade de interpolação da câmera (mais ágil)

# ── Índice do dispositivo de câmera do PC ─────────────────────────────
# Se None: o jogo detecta automaticamente o primeiro índice funcional.
# Se inteiro (ex: 0, 1, 2): força o uso do índice especificado.
CAMERA_INDEX = None
