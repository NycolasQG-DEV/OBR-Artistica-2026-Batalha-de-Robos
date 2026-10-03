import asyncio
import time
from typing import Dict, Type, Optional, Callable
from PySide6.QtCore import QObject, Signal

from engine.config import PresentationConfig, SlideConfig
from players.base_player import BaseSlidePlayer
from players.image_player import ImageSlidePlayer
from players.html_player import HTMLSlidePlayer
from players.audio_player import AudioSlidePlayer
from players.video_player import VideoSlidePlayer
from players.panda_player import PandaSlidePlayer
from players.cv_player import CVSlidePlayer
from players.selection_player import SelectionSlidePlayer
from players.serial_player import SerialScriptSlidePlayer
from players.calibration_player import HandCalibrationSlidePlayer

PLAYER_REGISTRY: Dict[str, Type[BaseSlidePlayer]] = {
    "image": ImageSlidePlayer,
    "html": HTMLSlidePlayer,
    "audio": AudioSlidePlayer,
    "video": VideoSlidePlayer,
    "panda3d": PandaSlidePlayer,
    "3d": PandaSlidePlayer,
    "cv": CVSlidePlayer,
    "vision": CVSlidePlayer,
    "selection": SelectionSlidePlayer,
    "select": SelectionSlidePlayer,
    "hero_select": SelectionSlidePlayer,
    "character_select": SelectionSlidePlayer,
    "calibration": HandCalibrationSlidePlayer,
    "hand_calibration": HandCalibrationSlidePlayer,
    "hand_detect": HandCalibrationSlidePlayer,
    "camera_hand": HandCalibrationSlidePlayer,
    "hand_open": HandCalibrationSlidePlayer,
    "hand": HandCalibrationSlidePlayer,
    "serial": SerialScriptSlidePlayer,
    "robot": SerialScriptSlidePlayer,
    "script": SerialScriptSlidePlayer,
    "descomplex": SerialScriptSlidePlayer,
    "esp32": SerialScriptSlidePlayer,
}

class SequenceRunner(QObject):
    slide_changed = Signal(int, object) # index, player_widget
    progress_updated = Signal(float)   # 0.0 to 1.0
    presentation_ended = Signal()
    game_preboot_signal = Signal(str)  # champion_name

    def __init__(self, config: PresentationConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_index = 0
        self.is_running = False
        self.is_paused = False
        self._skip_flag = False
        self.parent_widget = None
        self.current_player: Optional[BaseSlidePlayer] = None
        self.player_instances: Dict[int, BaseSlidePlayer] = {}
        self.selected_champion = "PenLinux"
        self._game_launched = False

    def get_or_create_player(self, index: int, parent_widget) -> Optional[BaseSlidePlayer]:
        if index in self.player_instances:
            return self.player_instances[index]

        slide_cfg = self.config.get_slide(index)
        if not slide_cfg:
            return None

        player_cls = PLAYER_REGISTRY.get(slide_cfg.type.lower(), HTMLSlidePlayer)
        player = player_cls(slide_cfg, parent=parent_widget)
        self.player_instances[index] = player
        return player

    async def start(self, parent_widget):
        """Start the presentation playback timeline loop."""
        self.is_running = True
        self.parent_widget = parent_widget
        self.current_index = 0
        self._game_launched = False

        # Pre-prepare all slides in background
        for idx in range(len(self.config.slides)):
            p = self.get_or_create_player(idx, parent_widget)
            if p:
                await p.prepare()

        while self.is_running:
            slide_cfg = self.config.get_slide(self.current_index)
            if not slide_cfg:
                break

            player = self.get_or_create_player(self.current_index, parent_widget)
            if not player:
                break

            self.current_player = player
            self.slide_changed.emit(self.current_index, player)

            # Play active slide
            await player.play()

            # Pré-boot imediato do jogo em segundo plano ao iniciar o slide que antecede a batalha
            # Isso elimina a tela preta carregando o Panda3D em paralelo com a reprodução do vídeo
            if slide_cfg.get("launch_game", False) or slide_cfg.get("preboot", False):
                if not self._game_launched:
                    self._game_launched = True
                    print(f"[SequenceRunner] Slide com launch_game ({slide_cfg.id}) iniciado! Pré-carregando jogo em segundo plano...")
                    self.game_preboot_signal.emit(self.selected_champion)

            if slide_cfg.type.lower() in ("selection", "select", "hero_select", "character_select", "calibration", "hand_calibration", "hand_detect", "camera_hand", "hand_open", "hand") or slide_cfg.wait_next <= 0:
                duration = float('inf')
            else:
                duration = slide_cfg.wait_next

            start_t = time.monotonic()
            accumulated_pause = 0.0

            step = 0.016 # ~60Hz timeline check

            while self.is_running and not self._skip_flag:
                if self.is_paused:
                    pause_start = time.monotonic()
                    while self.is_paused and self.is_running and not self._skip_flag:
                        await asyncio.sleep(0.05)
                    accumulated_pause += time.monotonic() - pause_start

                elapsed = (time.monotonic() - start_t) - accumulated_pause
                if elapsed >= duration:
                    # Check if this slide is meant to launch the game
                    if slide_cfg.get("launch_game", False):
                        if not self._game_launched:
                            self._game_launched = True
                            self.game_preboot_signal.emit(self.selected_champion)
                        
                        # Wait for the game process to finish
                        while self.is_running and not self._skip_flag:
                            main_win = self.parent_widget.window() if self.parent_widget else None
                            if main_win and hasattr(main_win, "game_process") and main_win.game_process:
                                if main_win.game_process.poll() is not None:
                                    print("[SequenceRunner] Jogo finalizado! Avançando para o Ato 3...")
                                    self._game_launched = False
                                    break
                            await asyncio.sleep(step)

                    break

                self.progress_updated.emit(min(1.0, elapsed / duration))
                await asyncio.sleep(step)

            # Stop active slide
            await player.stop()

            if not self._skip_flag:
                # Normal progression
                self.current_index += 1

            self._skip_flag = False

            if self.current_index >= len(self.config.slides):
                if self.config.loop:
                    self.current_index = 0
                else:
                    self.is_running = False
                    self.presentation_ended.emit()
                    break

    def stop(self):
        self.is_running = False

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def skip_next(self):
        """Skip to next slide manually (synchronous for Qt slots)."""
        if not self.config.slides:
            return
        self.current_index += 1
        self._skip_flag = True

    def skip_prev(self):
        """Skip to previous slide manually (synchronous for Qt slots)."""
        if not self.config.slides:
            return
        self.current_index = max(0, self.current_index - 1)
        self._skip_flag = True

    async def next_slide(self):
        self.skip_next()

    async def prev_slide(self):
        self.skip_prev()

