# game/config/serial.py — configurações da comunicação serial / ESP32
# (Herda as configurações universais do arquivo config.py no escopo raiz)

import os
import sys

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import config

DEV_MODE = config.DEV_MODE
SERIAL_PORT = config.SERIAL_PORT
SERIAL_BAUDRATE = config.SERIAL_BAUDRATE
SERIAL_TIMEOUT = config.SERIAL_TIMEOUT



