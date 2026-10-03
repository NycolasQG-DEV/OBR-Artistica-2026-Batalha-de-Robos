from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from engine.config import SlideConfig

class BaseSlidePlayer(QWidget):
    """Base class for all slide players."""

    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Style background
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

    async def prepare(self):
        """Async setup before slide becomes active."""
        pass

    async def play(self):
        """Called when the slide starts displaying."""
        pass

    async def stop(self):
        """Called when the slide ends displaying."""
        pass

