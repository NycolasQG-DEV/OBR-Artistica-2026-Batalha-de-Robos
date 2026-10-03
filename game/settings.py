# settings.py — Arquivo de Configurações do Jogo (Herda de config.py universal)

import os
import sys

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import config

DEV_MODE = config.DEV_MODE
SERIAL_PORT = config.SERIAL_PORT
SERIAL_BAUDRATE = config.SERIAL_BAUDRATE
SERIAL_TIMEOUT = config.SERIAL_TIMEOUT

# Re-exporta todas as configurações do jogo
from game.config.grid import *      # noqa: F401,F403
from game.config.camera import *    # noqa: F401,F403
from game.config.battle import *    # noqa: F401,F403
from game.config.states import *    # noqa: F401,F403
from game.config.colors import *    # noqa: F401,F403
from game.config.serial import *    # noqa: F401,F403

# Sincroniza as chaves do config.py universal com o módulo serial
import game.config.serial as _serial_cfg
_serial_cfg.DEV_MODE = config.DEV_MODE
_serial_cfg.SERIAL_PORT = config.SERIAL_PORT
_serial_cfg.SERIAL_BAUDRATE = config.SERIAL_BAUDRATE
_serial_cfg.SERIAL_TIMEOUT = config.SERIAL_TIMEOUT



