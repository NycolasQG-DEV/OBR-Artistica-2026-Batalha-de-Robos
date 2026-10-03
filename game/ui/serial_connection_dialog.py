"""ui/serial_connection_dialog.py — Diálogo Modal de Conexão Serial com o ESP32.

Bloqueia a inicialização do jogo até que a conexão serial via COM/Bluetooth com o robô
esteja 100% estabelecida e confirmada.
"""

import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame, QGroupBox
)


class SerialConnectionDialog(QDialog):
    """Diálogo modal que exige conexão serial ativa com o ESP32 antes do início do jogo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conexão Serial ESP32 — Robot Arena 3D")
        self.setFixedSize(540, 380)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        from game.combat.serial_controller import get_serial_controller
        self.sc = get_serial_controller()

        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f19;
                border: 2px solid #00ffcc;
                border-radius: 12px;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e0e6ed;
            }
            QComboBox {
                background-color: #161f30;
                border: 1px solid #00ffcc;
                border-radius: 6px;
                color: #00ffcc;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
            }
            QComboBox QAbstractItemView {
                background-color: #161f30;
                color: #00ffcc;
                selection-background-color: #00ffcc;
                selection-color: #000000;
            }
            QPushButton {
                background-color: rgba(0, 255, 204, 0.15);
                border: 1px solid #00ffcc;
                border-radius: 6px;
                color: #00ffcc;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 18px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 204, 0.35);
            }
            QPushButton#btn_dev {
                background-color: rgba(255, 102, 0, 0.15);
                border: 1px solid #ff6600;
                color: #ff6600;
            }
            QPushButton#btn_dev:hover {
                background-color: rgba(255, 102, 0, 0.35);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        # Cabeçalho
        lbl_title = QLabel("CONEXÃO SERIAL ESP32 REQUERIDA")
        lbl_title.setFont(QFont("Consolas", 15, QFont.Bold))
        lbl_title.setStyleSheet("color: #00ffcc; letter-spacing: 1px;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("O jogo aguarda a conexão com o robô físico via porta COM / Bluetooth para iniciar.")
        lbl_subtitle.setWordWrap(True)
        lbl_subtitle.setStyleSheet("font-size: 12px; color: #8a99ad;")
        lbl_subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_subtitle)

        # Caixas de Seleção e Status
        box = QGroupBox()
        box.setStyleSheet("border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 8px; background-color: #111726;")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(12)

        lbl_port_tag = QLabel("Porta COM do Robô (ESP32):")
        lbl_port_tag.setStyleSheet("font-size: 12px; font-weight: bold; color: #aabbcc;")
        box_layout.addWidget(lbl_port_tag)

        port_row = QHBoxLayout()
        self.combo_ports = QComboBox()
        self.btn_refresh = QPushButton("🔄 Atualizar Portas")
        self.btn_refresh.setFixedWidth(140)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.combo_ports, stretch=1)
        port_row.addWidget(self.btn_refresh)
        box_layout.addLayout(port_row)

        self.lbl_status = QLabel("⚡ Status: Procurando conexões seriais...")
        self.lbl_status.setFont(QFont("Consolas", 11, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #ffaa00; margin-top: 6px;")
        box_layout.addWidget(self.lbl_status)

        layout.addWidget(box)

        # Botões de Ação
        btn_row = QHBoxLayout()

        self.btn_connect = QPushButton("Conectar Robô e Iniciar Jogo")
        self.btn_connect.clicked.connect(self._on_click_connect)
        btn_row.addWidget(self.btn_connect, stretch=2)

        self.btn_dev = QPushButton("Ativar Modo Dev", objectName="btn_dev")
        self.btn_dev.clicked.connect(self._on_click_dev_mode)
        btn_row.addWidget(self.btn_dev, stretch=1)

        layout.addLayout(btn_row)

        # Timer para escaneamento e tentativa de conexão automática (a cada 1.5s)
        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(1500)
        self.scan_timer.timeout.connect(self._auto_check_connection)
        self.scan_timer.start()

        self._refresh_ports()
        self._auto_check_connection()

    def _refresh_ports(self):
        self.combo_ports.clear()
        self.combo_ports.addItem("AUTO (Busca Automática)", "AUTO")

        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for p in ports:
                label = f"{p.device} — {p.description}"
                self.combo_ports.addItem(label, p.device)
        except Exception:
            pass

    def _auto_check_connection(self):
        if self.sc.is_connected():
            self.lbl_status.setText("✅ CONEXÃO ESTABELECIDA COM SUCESSO! Iniciando...")
            self.lbl_status.setStyleSheet("color: #00ffcc; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            QTimer.singleShot(800, self.accept)
            return

        selected_port = self.combo_ports.currentData() or "AUTO"
        connected = self.sc.try_connect(selected_port)
        if connected:
            self.lbl_status.setText("✅ CONEXÃO ESTABELECIDA COM SUCESSO! Iniciando...")
            self.lbl_status.setStyleSheet("color: #00ffcc; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            QTimer.singleShot(800, self.accept)
        else:
            self.lbl_status.setText("⏳ Aguardando robô na porta COM / Bluetooth...")
            self.lbl_status.setStyleSheet("color: #ffaa00; font-weight: bold;")

    def _on_click_connect(self):
        selected_port = self.combo_ports.currentData() or "AUTO"
        if self.sc.try_connect(selected_port):
            self.lbl_status.setText("✅ CONEXÃO ESTABELECIDA COM SUCESSO! Iniciando...")
            self.lbl_status.setStyleSheet("color: #00ffcc; font-weight: bold;")
            QTimer.singleShot(500, self.accept)
        else:
            self.lbl_status.setText("❌ Erro ao conectar na porta selecionada. Verifique se o ESP32 está ligado.")
            self.lbl_status.setStyleSheet("color: #ff3366; font-weight: bold;")

    def _on_click_dev_mode(self):
        self.sc.dev_mode = True
        self.lbl_status.setText("⚠️ Modo Dev ativado (Executando em modo de simulação).")
        self.lbl_status.setStyleSheet("color: #ff6600; font-weight: bold;")
        QTimer.singleShot(500, self.accept)


def ensure_serial_connected_before_start() -> bool:
    """Verifica e exige conexão serial antes de iniciar a aplicação."""
    from game.combat.serial_controller import get_serial_controller
    sc = get_serial_controller()

    if sc.is_connected():
        print("[SerialConnection] Conexão serial prévia confirmada. Iniciando jogo...")
        return True

    print("[SerialConnection] Conexão serial necessária. Abrindo janela de aguardo da conexão...")
    dialog = SerialConnectionDialog()
    result = dialog.exec()
    return result == QDialog.Accepted or sc.is_connected()
