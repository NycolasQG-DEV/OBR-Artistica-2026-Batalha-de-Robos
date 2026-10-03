import os
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

class AudioSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)
        
        # Deixa a tela completamente transparente e remove qualquer design
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

    async def play(self):
        src = self.config.get("src")
        if src and os.path.exists(src):
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(src)))
            self.audio_output.setVolume(1.0)
            self.player.play()
        else:
            # Erro padrão no console sem crashar, permitindo que o wait_next passe normalmente
            print(f"[AudioSlidePlayer] ERRO: Áudio não encontrado ou inválido ('{src}'). Ignorando e prosseguindo com o jogo em background...")

    async def stop(self):
        self.player.stop()
