import os
import sys
import time
import asyncio
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QProgressBar,
    QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

GAME_DIR = os.path.join(ROOT_DIR, "game")
if GAME_DIR not in sys.path:
    sys.path.append(GAME_DIR)

try:
    from game.combat.serial_controller import get_serial_controller
    _HAS_SERIAL_CONTROLLER = True
except Exception:
    try:
        from combat.serial_controller import get_serial_controller
        _HAS_SERIAL_CONTROLLER = True
    except Exception as e:
        print(f"[SerialScript] Erro ao importar serial_controller: {e}")
        _HAS_SERIAL_CONTROLLER = False


class RobotScript:
    """Interface simples para programar movimentações robóticas em segundo plano com garantia de handshake serial OK."""

    def __init__(self, player, tag="PLAYER"):
        self.player = player
        self.sc = get_serial_controller() if _HAS_SERIAL_CONTROLLER else None
        self.tag = tag

    async def ensure_ready(self):
        """Garante que a porta serial esteja pronta e o 'ok' anterior tenha sido recebido antes de enviar o próximo comando."""
        if self.sc:
            await self.sc.wait_ok(self.tag)

    async def move_forward(self, tiles: float = 1.0, speed: int = 180):
        """Avança N tiles para frente, aguardando 'ok' antes e depois do envio para não quebrar a fila serial."""
        await self.ensure_ready()
        print(f"[RobotScript][{self.tag}] Avancando {tiles} tile(s) para frente (W)...")
        if self.sc:
            self.sc.write_command(self.tag, "W", tiles, speed)
            await self.sc.wait_ok(self.tag, "W")
        else:
            await asyncio.sleep(1.0)
        await asyncio.sleep(0.3)

    async def move_backward(self, tiles: float = 1.0, speed: int = 180):
        """Recua N tiles para trás, aguardando 'ok' antes e depois do envio."""
        await self.ensure_ready()
        print(f"[RobotScript][{self.tag}] Recuando {tiles} tile(s) para tras (S)...")
        if self.sc:
            self.sc.write_command(self.tag, "S", tiles, speed)
            await self.sc.wait_ok(self.tag, "S")
        else:
            await asyncio.sleep(1.0)
    async def turn(self, degrees: float = 90.0, speed: int = 180):
        """Gira o robô exatamente pelos graus e sinal especificados (ex: turn(90.0) ou turn(-90.0))."""
        await self.ensure_ready()
        print(f"[RobotScript][{self.tag}] Executando giro de {degrees} deg (TURN)...")
        if self.sc:
            self.sc.write_command(self.tag, "TURN", degrees, speed)
            await self.sc.wait_ok(self.tag, "TURN")
        else:
            await asyncio.sleep(1.0)
        await asyncio.sleep(0.3)

    async def turn_right(self, degrees: float = 90.0, speed: int = 180):
        """Gira N graus para a direita, aguardando 'ok' antes e depois do envio."""
        await self.ensure_ready()
        print(f"[RobotScript][{self.tag}] Girando {degrees} deg para a direita (TURN_RIGHT)...")
        if self.sc:
            self.sc.write_command(self.tag, "TURN_RIGHT", degrees, speed)
            await self.sc.wait_ok(self.tag, "TURN")
        else:
            await asyncio.sleep(1.0)
        await asyncio.sleep(0.3)

    async def turn_left(self, degrees: float = 90.0, speed: int = 180):
        """Gira N graus para a esquerda, aguardando 'ok' antes e depois do envio."""
        await self.ensure_ready()
        print(f"[RobotScript][{self.tag}] Girando {degrees} deg para a esquerda (TURN_LEFT)...")
        if self.sc:
            self.sc.write_command(self.tag, "TURN_LEFT", degrees, speed)
            await self.sc.wait_ok(self.tag, "TURN")
        else:
            await asyncio.sleep(1.0)
        await asyncio.sleep(0.3)

    async def play_sfx(self, sound_name: str = "whoosh.wav"):
        """Toca um efeito sonoro de áudio."""
        print(f"[RobotScript][{self.tag}] Tocando efeito sonoro ({sound_name})...")
        if hasattr(self.player, "play_sound_sfx"):
            self.player.play_sound_sfx(sound_name)
        await asyncio.sleep(1.0)

    async def sleep(self, seconds: float):
        """Pausa a execução por N segundos."""
        await asyncio.sleep(seconds)


# ═══════════════════════════════════════════════════════════════════════
# 🎯 PROGRAMAÇÃO DA SEQUÊNCIA DE MOVIMENTO EM SEGUNDO PLANO (SEM INTERFACE)
# ═══════════════════════════════════════════════════════════════════════
import importlib

async def custom_robot_sequence(player_instance):
    """Executa ESTRITAMENTE E APENAS a sequência definida no arquivo robot_sequence.py."""
    import robot_sequence
    importlib.reload(robot_sequence)

    print("[SerialScript] Executando ESTRITAMENTE a sequencia do arquivo robot_sequence.py...")
    db = RobotScript(player_instance, "PLAYER")
    pen = RobotScript(player_instance, "BOSS")
    await robot_sequence.run_sequence(db, pen)


_BACKGROUND_TASKS = set()

async def run_background_robot_script(player_instance):
    """Executa a sequência de movimentos em segundo plano em paralelo com a exibição de mídia."""
    print("[SerialScript] === INICIANDO MOVIMENTAÇÃO SERIAL EM SEGUNDO PLANO (PARALELO AO VÍDEO) ===")
    try:
        await custom_robot_sequence(player_instance)
        print("[SerialScript] === MOVIMENTAÇÃO SERIAL DE SEGUNDO PLANO CONCLUÍDA COM SUCESSO ===")
    except Exception as e:
        print(f"[SerialScript] Exceção na movimentação serial em segundo plano: {e}")


def launch_background_robot_script(player_instance):
    """Dispara a execução do script serial mantendo uma referência forte para evitar GC prematuro (Task pending warning)."""
    task = asyncio.create_task(run_background_robot_script(player_instance))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


class SerialScriptSlidePlayer(BaseSlidePlayer):
    """Slide de Execução de Comandos Seriais Descomplexados com Asyncio (Suporte Standalone)."""

    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)
        self.audio_player = None
        self.audio_output = None

        self.setStyleSheet("background-color: #050811;")
        self.layout.setContentsMargins(50, 40, 50, 40)
        self.layout.setSpacing(25)

        self.lbl_header = QLabel("🤖 SEQUÊNCIA SERIAL ROBÓTICA (PARALELA) 🤖", self)
        self.lbl_header.setAlignment(Qt.AlignCenter)
        self.lbl_header.setStyleSheet("font-size: 36px; font-weight: 900; color: #00f0ff;")
        self.layout.addWidget(self.lbl_header)

    async def prepare(self):
        if self.audio_player is None:
            try:
                self.audio_player = QMediaPlayer(self)
                self.audio_output = QAudioOutput(self)
                self.audio_player.setAudioOutput(self.audio_output)
                self.audio_output.setVolume(1.0)
            except Exception as e:
                print(f"[SerialScriptSlidePlayer] Erro inicializando áudio: {e}")

    async def _run_serial_script(self, src, champion_name):
        mod_name = os.path.splitext(os.path.basename(src))[0]
        try:
            import importlib
            import inspect
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            print(f"[SerialScriptSlidePlayer] Executando o arquivo {src} com campeão {champion_name} em SEGUNDO PLANO...")
            
            db = RobotScript(self, "PLAYER")
            pen = RobotScript(self, "BOSS")
            
            if hasattr(mod, "run_sequence"):
                sig = inspect.signature(mod.run_sequence)
                if len(sig.parameters) >= 3:
                    await mod.run_sequence(db, pen, champion_name)
                elif len(sig.parameters) == 2:
                    await mod.run_sequence(db, pen)
                else:
                    await mod.run_sequence(db)
        except Exception as e:
            print(f"[SerialScriptSlidePlayer] Erro ao carregar script {src}: {e}")

    async def play(self):
        src = self.config.get("src", "robot_sequence.py")
        main_win = self.window()
        champion_name = "PenLinux"
        if main_win and hasattr(main_win, "selected_champion") and main_win.selected_champion:
            champion_name = main_win.selected_champion

        # Lança a execução em segundo plano
        task = asyncio.create_task(self._run_serial_script(src, champion_name))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)

        # Avança imediatamente para o próximo slide para que este slide seja ignorado visualmente
        self._advance_slide()

    def play_sound_sfx(self, sound_name: str = "whoosh.wav"):
        sfx_path = os.path.abspath(os.path.join(GAME_DIR, "assets", "sounds", sound_name))
        if not os.path.exists(sfx_path):
            sfx_path = os.path.abspath(os.path.join(GAME_DIR, "assets", "sounds", "whoosh.wav"))

        if os.path.exists(sfx_path) and self.audio_player:
            self.audio_player.setSource(QUrl.fromLocalFile(sfx_path))
            self.audio_player.play()

    def _advance_slide(self):
        main_win = self.window()
        if main_win and hasattr(main_win, "runner"):
            main_win.runner.skip_next()
