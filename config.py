# config.py — Arquivo de Configuração Universal do Projeto SlideEngine & Robot Arena 3D
# ══════════════════════════════════════════════════════════════════════════════
# Todas as configurações globais principais do SlideEngine e do Jogo devem ser
# alteradas neste arquivo. Ele é a FONTE ÚNICA DE VERDADE ("Lei Central") do projeto.
# ══════════════════════════════════════════════════════════════════════════════

# ------------------------------------------------------------------------------
# 1. MODO DE DESENVOLVIMENTO (DEV_MODE)
# ------------------------------------------------------------------------------
# True  = MODO DEV ATIVO:
#         - Abre a Janela Visualizadora do Robô Virtual ESP32 em 2D.
#         - Simula o robô físico e envia a resposta 'ok' para o jogo avançar.
#         - NÃO tenta se conectar a NENHUMA porta COM serial.
#
# False = MODO HARDWARE REAL:
#         - Conecta à porta serial física COM via Bluetooth/UART (ex: "COM7", "COM8").
#         - Envia os comandos brutos pela serial e aguarda o 'ok' real do ESP32.
# ------------------------------------------------------------------------------
DEV_MODE: bool = True

# ------------------------------------------------------------------------------
# 2. COMUNICAÇÃO SERIAL / ESP32
# ------------------------------------------------------------------------------
# Porta serial COM do ESP32/Robô (ex: "COM7", "COM8", "AUTO")
SERIAL_PORT: str = "COM8"

# Baudrate da comunicação serial com o ESP32 (padrão firmware .ino: 115200)
SERIAL_BAUDRATE: int = 115200

# Tempo máximo em segundos para aguardar a resposta 'ok' do ESP32
SERIAL_TIMEOUT: float = 10.0

# ------------------------------------------------------------------------------
# 3. APRESENTAÇÃO & SLIDE ENGINE
# ------------------------------------------------------------------------------
# Arquivo JSON contendo a sequência e estrutura dos slides
SEQUENCE_FILE: str = "sequence.json"

# Tempo padrão em segundos de exibição de slides sem duração explícita
DEFAULT_SLIDE_WAIT: float = 5.0

# Se True, reinicia a apresentação após o término do último slide
LOOP_PRESENTATION: bool = True
