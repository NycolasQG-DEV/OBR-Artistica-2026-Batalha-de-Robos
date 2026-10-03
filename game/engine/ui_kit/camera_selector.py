import sys
import os
import time
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QImage, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame, QGraphicsDropShadowEffect
)

COLOR_CYAN   = "#00ecff"
COLOR_GREEN  = "#23ff78"
COLOR_ORANGE = "#ff6600"
COLOR_RED    = "#ff2244"
COLOR_YELLOW = "#ffcc00"
COLOR_BG     = "#04070d"
COLOR_CARD_BG = "rgba(8, 14, 28, 0.92)"
FONT_HUD = "Bahnschrift, Segoe UI Semibold, Arial Black, sans-serif"
FONT_MONO = "Cascadia Code, Consolas, monospace"


class CameraScanWorker(QThread):
    """Background thread to scan for available cameras using OpenCV."""
    finished_scan = Signal(list)

    def run(self):
        try:
            import cv2
        except ImportError:
            self.finished_scan.emit([])
            return

        available = []
        # Try camera indices 0 to 5
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
            if cap is not None:
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        available.append(i)
                    cap.release()
        self.finished_scan.emit(available)


class CameraPreviewWorker(QThread):
    """Background thread for capturing live frames from the selected webcam."""
    frame_ready = Signal(QImage)

    def __init__(self, index):
        super().__init__()
        self.index = index
        self.running = True

    def run(self):
        try:
            import cv2
        except ImportError:
            return

        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
        if cap is None or not cap.isOpened():
            return

        # Attempt to request standard video dimensions
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Flip horizontally for mirrored view (intuitive webcam preview)
            frame = cv2.flip(frame, 1)

            # Convert OpenCV's BGR to Qt's RGB format
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # Wrap in a QImage and copy to ensure memory safety
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            qimg_copy = qimg.copy()

            self.frame_ready.emit(qimg_copy)
            time.sleep(0.033)  # limit frame rate (~30 FPS)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()


class CameraSelectorDialog(QDialog):
    """Modern dark themed dialog for selecting webcams prior to running the main game."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 560)

        self.selected_index = 0
        self.preview_worker = None
        self.available_cameras = []

        # Main window layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Styled neon container frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_CARD_BG};
                border: 2px solid {COLOR_CYAN};
                border-radius: 16px;
            }}
        """)
        
        # Shadow glow effect
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(QColor(0, 236, 255, 120))
        self.shadow.setOffset(0, 0)
        self.frame.setGraphicsEffect(self.shadow)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(24, 28, 24, 28)
        frame_layout.setSpacing(16)

        # Title
        self.lbl_title = QLabel("SELECIONE A CÂMERA", self.frame)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 22px;
            font-weight: bold;
            color: {COLOR_YELLOW};
            letter-spacing: 1.5px;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(self.lbl_title)

        # Subtitle
        self.lbl_subtitle = QLabel("Posicione-se em um local bem iluminado para o Hand Tracking.", self.frame)
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle.setStyleSheet(f"""
            font-family: {FONT_HUD};
            font-size: 13px;
            color: #8a9fc4;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(self.lbl_subtitle)

        # Video Preview display area
        self.lbl_preview = QLabel(self.frame)
        self.lbl_preview.setFixedSize(360, 270)
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet(f"""
            QLabel {{
                background-color: #020408;
                border: 1.5px dashed rgba(0, 236, 255, 0.4);
                border-radius: 8px;
                color: #8a9fc4;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
        """)
        self.lbl_preview.setText("DETECTANDO CÂMERAS...")
        frame_layout.addWidget(self.lbl_preview, 0, Qt.AlignCenter)

        # Camera selector Dropdown
        self.combo_cameras = QComboBox(self.frame)
        self.combo_cameras.setFixedHeight(40)
        self.combo_cameras.setFixedWidth(360)
        self.combo_cameras.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: white;
                font-family: {FONT_HUD};
                font-size: 14px;
                font-weight: 600;
                padding-left: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                margin-right: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_BG};
                border: 1.5px solid {COLOR_CYAN};
                border-radius: 8px;
                color: white;
                selection-background-color: rgba(0, 236, 255, 0.2);
                outline: none;
            }}
        """)
        self.combo_cameras.addItem("Procurando dispositivos de vídeo...")
        self.combo_cameras.setEnabled(False)
        self.combo_cameras.currentIndexChanged.connect(self._on_camera_changed)
        frame_layout.addWidget(self.combo_cameras, 0, Qt.AlignCenter)

        # Buttons area
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)

        # Button: SAIR
        self.btn_exit = QPushButton("SAIR", self.frame)
        self.btn_exit.setFixedHeight(45)
        self.btn_exit.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 34, 68, 0.08);
                border: 1.5px solid {COLOR_RED};
                border-radius: 10px;
                color: {COLOR_RED};
                font-family: {FONT_HUD};
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_RED};
                color: white;
            }}
        """)
        self.btn_exit.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_exit)

        # Button: INICIAR JOGO
        self.btn_start = QPushButton("INICIAR JOGO", self.frame)
        self.btn_start.setFixedHeight(45)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(35, 255, 120, 0.08);
                border: 1.5px solid {COLOR_GREEN};
                border-radius: 10px;
                color: {COLOR_GREEN};
                font-family: {FONT_HUD};
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_GREEN};
                color: #04070d;
            }}
            QPushButton:disabled {{
                border-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 0.3);
                background-color: rgba(255, 255, 255, 0.02);
            }}
        """)
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.btn_start)

        frame_layout.addLayout(btn_layout)
        layout.addWidget(self.frame)

        # Execute background scan for cameras
        self.scan_worker = CameraScanWorker()
        self.scan_worker.finished_scan.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_finished(self, cameras):
        self.available_cameras = cameras
        self.combo_cameras.blockSignals(True)
        self.combo_cameras.clear()

        if cameras:
            for idx in cameras:
                self.combo_cameras.addItem(f"CÂMERA {idx}", idx)
            self.combo_cameras.setEnabled(True)
            self.btn_start.setEnabled(True)
            self.combo_cameras.blockSignals(False)
            # Trigger preview for the first camera
            self._start_preview(cameras[0])
        else:
            self.combo_cameras.addItem("NENHUMA CÂMERA DETECTADA", -1)
            self.combo_cameras.blockSignals(False)
            # Keep startup active, since user can fallback to mouse controls
            self.btn_start.setEnabled(True)
            self.lbl_preview.setText("SEM SINAL DE VÍDEO\nO JOGO SERÁ EXECUTADO COM MOUSE")

    def _start_preview(self, index):
        self._stop_preview()
        self.lbl_preview.setText("CONECTANDO A CÂMERA...")
        self.preview_worker = CameraPreviewWorker(index)
        self.preview_worker.frame_ready.connect(self._update_preview_label)
        self.preview_worker.start()

    def _stop_preview(self):
        if self.preview_worker:
            try:
                self.preview_worker.frame_ready.disconnect(self._update_preview_label)
            except Exception:
                pass
            self.preview_worker.stop()
            self.preview_worker = None

    def _update_preview_label(self, qimg):
        # Resize QImage nicely matching preview display dimensions
        scaled_pix = QPixmap.fromImage(qimg).scaled(
            self.lbl_preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.lbl_preview.setPixmap(scaled_pix)

    def _on_camera_changed(self, index_of_combo):
        if index_of_combo < 0:
            return
        camera_idx = self.combo_cameras.itemData(index_of_combo)
        if camera_idx >= 0:
            self._start_preview(camera_idx)

    def _on_start_clicked(self):
        # Write chosen index to config file
        choice_idx = 0
        current_combo_idx = self.combo_cameras.currentIndex()
        if current_combo_idx >= 0:
            val = self.combo_cameras.itemData(current_combo_idx)
            if val is not None and val >= 0:
                choice_idx = val

        try:
            with open("camera_choice.txt", "w") as f:
                f.write(str(choice_idx))
            print(f"[CameraSelector] Wrote choice {choice_idx} to camera_choice.txt")
        except Exception as e:
            print(f"[CameraSelector] Error writing camera choice: {e}")

        self._stop_preview()
        self.accept()

    def reject(self):
        self._stop_preview()
        super().reject()

    def closeEvent(self, event):
        self._stop_preview()
        if self.scan_worker:
            self.scan_worker.wait()
        super().closeEvent(event)
