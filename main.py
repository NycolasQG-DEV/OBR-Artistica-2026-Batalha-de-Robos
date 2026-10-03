import sys
import os
import asyncio
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QKeyEvent

from engine.config import PresentationConfig
from engine.runner import SequenceRunner

# ==============================================================================
# CONFIGURAÇÕES UNIVERSAIS DO SLIDE ENGINE E JOGO (config.py)
# ==============================================================================
import sys
import os
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
game_dir = os.path.abspath(os.path.join(root_dir, "game"))
if game_dir not in sys.path:
    sys.path.insert(0, game_dir)

from config import DEV_MODE, SERIAL_PORT, SEQUENCE_FILE
# ==============================================================================


class SlideEngineWindow(QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self.config = PresentationConfig(config_path)

        self.setWindowTitle(f"Slide Engine Fullscreen — {self.config.title}")
        # Fullscreen frameless window by default using native screen geometry
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.bars_visible = True

        # Central Widget & Main Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar
        self.header = QFrame(self)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-bottom: 2px solid rgba(0, 240, 255, 0.2);
            }
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        self.lbl_title = QLabel(f"🚀 {self.config.title}", self)
        self.lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00f0ff;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.lbl_help_hint = QLabel("[F11] Tela Cheia  |  [H] Ocultar Barras  |  [Espaço] Pausar  |  [← / →] Slides", self)
        self.lbl_help_hint.setStyleSheet("font-size: 13px; color: #64748b; margin-right: 20px;")
        header_layout.addWidget(self.lbl_help_hint)

        self.lbl_slide_counter = QLabel("Slide 1 / 1", self)
        self.lbl_slide_counter.setStyleSheet("font-size: 16px; color: #94a3b8; font-weight: bold;")
        header_layout.addWidget(self.lbl_slide_counter)

        main_layout.addWidget(self.header)

        # Slide Stack Viewport
        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet("background-color: #070a13;")
        main_layout.addWidget(self.stack, stretch=1)

        # Footer / Progress & Controls
        self.footer = QFrame(self)
        self.footer.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(20, 8, 20, 8)
        footer_layout.setSpacing(6)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00f0ff, stop:1 #ff007f);
                border-radius: 3px;
            }
        """)
        footer_layout.addWidget(self.progress_bar)

        # Controls bar
        controls_layout = QHBoxLayout()

        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #00f0ff;
                border: 1px solid rgba(0, 240, 255, 0.4);
                padding: 6px 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #00f0ff;
                color: #0f172a;
            }
        """

        self.btn_prev = QPushButton("⏮ ANTERIOR", self)
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.clicked.connect(self._prev_slide)
        controls_layout.addWidget(self.btn_prev)

        self.btn_pause = QPushButton("⏸ PAUSAR", self)
        self.btn_pause.setStyleSheet(btn_style)
        self.btn_pause.clicked.connect(self._toggle_pause)
        controls_layout.addWidget(self.btn_pause)

        self.btn_next = QPushButton("PRÓXIMO ⏭", self)
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.clicked.connect(self._next_slide)
        controls_layout.addWidget(self.btn_next)

        self.lbl_status = QLabel("● REPRODUZINDO SEQUÊNCIA ASYNC", self)
        self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px; margin-left: 15px;")
        controls_layout.addWidget(self.lbl_status)

        controls_layout.addStretch()

        self.btn_hide_bars = QPushButton("👁 OCULTAR BARRAS (H)", self)
        self.btn_hide_bars.setStyleSheet(btn_style)
        self.btn_hide_bars.clicked.connect(self.toggle_bars)
        controls_layout.addWidget(self.btn_hide_bars)

        self.btn_fullscreen = QPushButton("⛶ TELA CHEIA (F11)", self)
        self.btn_fullscreen.setStyleSheet(btn_style)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        controls_layout.addWidget(self.btn_fullscreen)

        footer_layout.addLayout(controls_layout)
        main_layout.addWidget(self.footer)

        # Initialize Runner
        self.selected_champion = "PenLinux"
        self.runner = SequenceRunner(self.config, self)
        self.runner.slide_changed.connect(self._on_slide_changed)
        self.runner.progress_updated.connect(self._on_progress_updated)
        self.runner.game_preboot_signal.connect(self._on_game_preboot)
        self.runner.presentation_ended.connect(self._on_presentation_ended)

        # Hide all bars by default for clean media fullscreen view
        self.bars_visible = False
        self.header.hide()
        self.footer.hide()

    def _on_game_preboot(self, champion_name: str):
        game_dir = os.path.abspath("game")
        game_script = os.path.join(game_dir, "main.py")
        print(f"[main.py] PRÉ-CARREGAMENTO ATIVADO ({champion_name})! Lançando o jogo em segundo plano em paralelo com o vídeo...")

        # Libera a porta serial para que o jogo possa assumi-la
        if not DEV_MODE:
            try:
                from game.combat.serial_controller import get_serial_controller
                sc = get_serial_controller()
                sc.close()
                print("[main.py] Porta serial liberada para o jogo.")
            except Exception as e:
                pass

        try:
            import subprocess
            cmd = [sys.executable, game_script, "--robot", champion_name]
            self.game_process = subprocess.Popen(cmd, cwd=game_dir)
        except Exception as e:
            print(f"[main.py] Erro ao disparar jogo em segundo plano: {e}")

    def _on_presentation_ended(self):
        print(f"[main.py] Apresentação e vídeo concluídos! Encerrando o SlideEngine.")
        
        # Garante a liberação da porta serial no encerramento
        if not DEV_MODE:
            try:
                from game.combat.serial_controller import get_serial_controller
                sc = get_serial_controller()
                sc.close()
            except Exception:
                pass

        self.close()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fullscreen.setText("⛶ TELA CHEIA (F11)")
        else:
            self.showFullScreen()
            self.btn_fullscreen.setText("🗗 JANELA (F11)")

    def toggle_bars(self):
        self.bars_visible = not self.bars_visible
        if self.bars_visible:
            self.header.show()
            self.footer.show()
        else:
            self.header.hide()
            self.footer.hide()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_F11, Qt.Key_F):
            self.toggle_fullscreen()
        elif key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_Space:
            self._toggle_pause()
        elif key in (Qt.Key_H, Qt.Key_Tab):
            self.toggle_bars()
        elif key == Qt.Key_Right:
            self._next_slide()
        elif key == Qt.Key_Left:
            self._prev_slide()
        else:
            super().keyPressEvent(event)

    def _next_slide(self):
        self.runner.skip_next()

    def _prev_slide(self):
        self.runner.skip_prev()

    def _on_slide_changed(self, index: int, player_widget: QWidget):
        total = len(self.config.slides)
        self.lbl_slide_counter.setText(f"Slide {index + 1} / {total}")
        
        # Make the stack background transparent for audio to show the game behind
        slide_type = getattr(player_widget.config, "type", "").lower()
        if slide_type == "audio":
            self.stack.setStyleSheet("background-color: transparent;")
        else:
            self.stack.setStyleSheet("background-color: #070a13;")

        # Add to stack if not present
        if self.stack.indexOf(player_widget) == -1:
            self.stack.addWidget(player_widget)

        self.stack.setCurrentWidget(player_widget)
        self.progress_bar.setValue(0)

    def _on_progress_updated(self, frac: float):
        self.progress_bar.setValue(int(frac * 1000))

    def _toggle_pause(self):
        if self.runner.is_paused:
            self.runner.resume()
            self.btn_pause.setText("⏸ PAUSAR")
            self.lbl_status.setText("● REPRODUZINDO SEQUÊNCIA ASYNC")
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px; margin-left: 15px;")
        else:
            self.runner.pause()
            self.btn_pause.setText("▶ CONTINUAR")
            self.lbl_status.setText("⏸ PAUSADO")
            self.lbl_status.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 14px; margin-left: 15px;")

def main():
    app = QApplication(sys.argv)

    # 🔌 Conecta à porta serial do ESP32 ANTES de iniciar a apresentação de verdade
    if not DEV_MODE:
        game_dir = os.path.abspath("game")
        if game_dir not in sys.path:
            sys.path.insert(0, game_dir)
        try:
            from game.combat.serial_controller import get_serial_controller
            sc = get_serial_controller()
            print(f"[main.py] Estabelecendo conexao especificamente com a porta serial {SERIAL_PORT}...")
            connected = sc.ensure_connected(SERIAL_PORT, max_retries=5, retry_interval=0.5)
            if connected:
                print(f"[main.py] CONEXAO SERIAL ESTABELECIDA COM SUCESSO! (Porta: {sc.port_name})")
            else:
                print(f"[main.py] AVISO: Nao foi possivel conectar a porta serial ({sc.port_name}). Operando no modo de simulacao.")
        except Exception as e:
            print(f"[main.py] Erro ao conectar porta serial no startup: {e}")
    else:
        print("[main.py] [DEV_MODE] Inicializacao rapida iniciada. Nenhuma conexao serial sera tentada pelo SlideEngine.")

    config_file = SEQUENCE_FILE

    if not os.path.exists(config_file):
        print(f"Erro: {config_file} não encontrado.")
        return

    window = SlideEngineWindow(config_file)
    window.show()

    # Zero-latency Qt-Asyncio integration event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start presentation async runner
    loop.create_task(window.runner.start(window.stack))

    # High performance QTimer pump for asyncio tasks
    pump_timer = QTimer()
    pump_timer.setInterval(10)

    def _pump_asyncio():
        try:
            loop.stop()
            loop.run_until_complete(asyncio.sleep(0.001))
        except Exception:
            pass

    pump_timer.timeout.connect(_pump_asyncio)
    pump_timer.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()