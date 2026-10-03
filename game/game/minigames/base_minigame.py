# combat/minigames/base_minigame.py — Classe base abstrata para minigames de ataque
"""
Cada minigame de ataque herda desta classe e implementa:
  - instruction_text: mensagem mostrada antes do minigame
  - duration: duração em segundos do minigame ativo
  - start(): chamado quando o minigame começa (após a instrução)
  - update(hand_pos, hand_closed, dt): chamado cada frame com dados de CV
  - get_result(): retorna "excellent", "good" ou "poor"
  - is_finished(): True quando o minigame terminou
  - paint(painter, width, height): renderiza os visuais do minigame
"""
import time
from abc import ABC, abstractmethod


class BaseAttackMinigame(ABC):
    """Base class for attack minigames using computer vision."""

    # Subclasses must define these
    instruction_text: str = "PREPARE-SE!"
    instruction_icon: str = "*"
    duration: float = 3.5  # seconds of active gameplay

    def __init__(self):
        self._started = False
        self._finished = False
        self._start_time = 0.0
        self._elapsed = 0.0
        self._result = "good"

    def start(self):
        """Called when the minigame begins (after instruction screen)."""
        self._started = True
        self._finished = False
        self._start_time = time.time()
        self._elapsed = 0.0
        self.on_start()

    def on_start(self):
        """Override to initialize game-specific state."""
        pass

    def update(self, hand_pos: tuple | None, hand_closed: bool, dt: float):
        """Called every frame with CV data.
        
        Args:
            hand_pos: (nx, ny) normalized 0-1, or None if no hand detected
            hand_closed: True if hand is in fist gesture
            dt: delta time in seconds
        """
        if not self._started or self._finished:
            return

        self._elapsed = time.time() - self._start_time

        if self._elapsed >= self.duration:
            self._finished = True
            self._result = self.evaluate()
            self.on_finish()
            return

        self.on_update(hand_pos, hand_closed, dt)

    @abstractmethod
    def on_update(self, hand_pos: tuple | None, hand_closed: bool, dt: float):
        """Override with game-specific update logic."""
        pass

    @abstractmethod
    def evaluate(self) -> str:
        """Override to evaluate final result. Returns 'excellent', 'good', or 'poor'."""
        return "good"

    def on_finish(self):
        """Override for cleanup when minigame ends."""
        pass

    def is_finished(self) -> bool:
        return self._finished

    def get_result(self) -> str:
        return self._result

    def get_time_remaining(self) -> float:
        """Returns time remaining in seconds."""
        if not self._started:
            return self.duration
        return max(0.0, self.duration - self._elapsed)

    def get_time_fraction(self) -> float:
        """Returns fraction of time remaining (1.0 = full, 0.0 = expired)."""
        if not self._started:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self._elapsed / self.duration))

    @abstractmethod
    def paint(self, painter, width: int, height: int, scale: float):
        """Render the minigame's visual elements using QPainter.
        
        Args:
            painter: QPainter instance already set up
            width: viewport width in pixels
            height: viewport height in pixels
            scale: UI scale factor
        """
        pass
