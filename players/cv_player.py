import cv2
import numpy as np
import time
import math
from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

class CVSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.lbl_video = QLabel(self)
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.lbl_video)

        self.cap = None
        self.timer = QTimer(self)
        self.timer.setInterval(16) # ~60 FPS
        self.timer.timeout.connect(self._process_frame)

        self.frame_count = 0
        self.start_time = time.time()

    async def prepare(self):
        # Initialize OpenCV Camera capture
        try:
            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if cv2.os.name == 'nt' else cv2.CAP_ANY)
            if not self.cap.isOpened():
                self.cap = None
        except Exception as e:
            print(f"[CVSlidePlayer] Erro na câmera OpenCV: {e}")
            self.cap = None

    async def play(self):
        self.frame_count = 0
        self.start_time = time.time()
        self.timer.start()

    async def stop(self):
        self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None

    def _process_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                frame = self._generate_synthetic_cv_frame()
        else:
            frame = self._generate_synthetic_cv_frame()

        filter_type = self.config.get("filter", "cyberpunk_edges")

        # Apply Computer Vision Filters
        if filter_type == "cyberpunk_edges":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            # Tint edges neon cyan
            edges_bgr[:, :, 0] = cv2.add(edges_bgr[:, :, 0], 200) # Blue
            edges_bgr[:, :, 1] = cv2.add(edges_bgr[:, :, 1], 200) # Green
            frame = cv2.addWeighted(frame, 0.6, edges_bgr, 0.4, 0)

        # FPS overlay (only if explicitly enabled in slide config)
        self.frame_count += 1
        if self.config.get("show_fps", False):
            elapsed = max(0.001, time.time() - self.start_time)
            fps = self.frame_count / elapsed
            cv2.putText(frame, f"CV PIPELINE | FPS: {fps:.1f} | FILTER: {filter_type.upper()}",
                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 240, 255), 2)

        # Target size in label while keeping aspect ratio
        lbl_w = max(100, self.lbl_video.width())
        lbl_h = max(100, self.lbl_video.height())
        fh, fw = frame.shape[:2]

        scale = min(lbl_w / fw, lbl_h / fh)
        target_w = max(1, int(fw * scale))
        target_h = max(1, int(fh * scale))

        # SIMD-accelerated fast resize in C++ (OpenCV)
        resized_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)

        # Memory-safe QImage creation from byte buffer
        qimg = QImage(rgb_frame.data.tobytes(), target_w, target_h, target_w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.lbl_video.setPixmap(pixmap)

    def _generate_synthetic_cv_frame(self) -> np.ndarray:
        w, h = 640, 480
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Generate synthetic grid and moving shapes for CV processing demo
        t = time.time()
        cx = int(w / 2 + math.sin(t * 2) * 150)
        cy = int(h / 2 + math.cos(t * 2) * 100)

        cv2.circle(frame, (cx, cy), 50, (0, 0, 255), -1)
        cv2.rectangle(frame, (cx - 80, cy - 80), (cx + 80, cy + 80), (255, 255, 0), 2)

        # Grid lines
        for x in range(0, w, 40):
            cv2.line(frame, (x, 0), (x, h), (40, 40, 40), 1)
        for y in range(0, h, 40):
            cv2.line(frame, (0, y), (w, y), (40, 40, 40), 1)

        return frame

