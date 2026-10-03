import os
import math
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QUrl, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

class FallbackCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0.0

    def update_frame(self):
        self.angle += 0.05
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(10, 15, 25))

        # Draw animated video simulation graphics
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.25

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor(0, 240, 255, 200))
        grad.setColorAt(1.0, QColor(255, 0, 128, 200))

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle * 50)
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRect(-r, -r, r * 2, r * 2)
        painter.restore()

        font = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(0, h - 100, w, 60), Qt.AlignCenter, "🎬 Sincronização de Vídeo & Áudio")

class VideoSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.video_widget)

        self.fallback_widget = FallbackCanvas(self)
        self.fallback_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.fallback_widget)
        self.fallback_widget.hide()

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.fallback_timer = QTimer(self)
        self.fallback_timer.setInterval(33)
        self.fallback_timer.timeout.connect(self.fallback_widget.update_frame)

        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.config.get("launch_game", False):
                # O jogo está sendo lançado; pausa no último frame para evitar tela preta até o jogo tomar o foco
                safe_pos = max(0, self.player.duration() - 200)
                self.player.setPosition(safe_pos)
                self.player.pause()
                return
                
            if getattr(self.config, "wait_next", 1.0) <= 0:
                # O vídeo e áudio chegaram ao fim absoluto.
                # Agora usamos a margem (ex: últimos 120 frames) para travar a tela.
                # Voltamos 2000ms (2 segundos) garantindo um frame estático e pausamos.
                safe_pos = max(0, self.player.duration() - 2000)
                self.player.setPosition(safe_pos)
                self.player.pause()
                return
                
            main_win = self.window()
            if main_win and hasattr(main_win, "runner"):
                main_win.runner.skip_next()

    async def prepare(self):
        src = self.config.get("src")
        if src and os.path.exists(src):
            self.video_widget.show()
            self.fallback_widget.hide()
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(src)))
        else:
            # Show animated fallback if video file not provided
            self.video_widget.hide()
            self.fallback_widget.show()

    async def play(self):
        src = self.config.get("src")
        if src and os.path.exists(src):
            self.video_widget.show()
            self.fallback_widget.hide()
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(src)))
            self.audio_output.setVolume(1.0)
            self.player.play()
        else:
            self.fallback_timer.start()

        # Executa a movimentação serial de fundo em paralelo se serial_script=True no sequence.json
        if self.config.get("serial_script") or self.config.get("script"):
            from players.serial_player import launch_background_robot_script
            self._serial_background_task = launch_background_robot_script(self)

    def play_sound_sfx(self, sound_name: str = "whoosh.wav"):
        game_dir = os.path.abspath("game")
        sfx_path = os.path.abspath(os.path.join(game_dir, "assets", "sounds", sound_name))
        if not os.path.exists(sfx_path):
            sfx_path = os.path.abspath(os.path.join(game_dir, "assets", "sounds", "whoosh.wav"))

        if os.path.exists(sfx_path):
            if not hasattr(self, "sfx_player") or self.sfx_player is None:
                self.sfx_player = QMediaPlayer(self)
                self.sfx_output = QAudioOutput(self)
                self.sfx_player.setAudioOutput(self.sfx_output)
                self.sfx_output.setVolume(1.0)
            self.sfx_player.setSource(QUrl.fromLocalFile(sfx_path))
            self.sfx_player.play()

    async def stop(self):
        self.player.stop()
        self.fallback_timer.stop()
        if hasattr(self, "sfx_player") and self.sfx_player:
            self.sfx_player.stop()
