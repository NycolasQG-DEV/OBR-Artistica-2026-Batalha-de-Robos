# input/cv_input.py — HandTracker usando mediapipe tasks API (sem solutions)
"""
Usa a API moderna mediapipe.tasks.python.vision.HandLandmarker.
Requer o arquivo hand_landmarker.task no mesmo diretório ou em ~/hand_landmarker.task.

Download manual (uma vez):
  wget -O hand_landmarker.task \
    https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

Sem o arquivo .task, o módulo usa fallback de mouse (cursor em (0.5, 0.5)).
"""

_HAS_CV2 = False
try:
    import cv2
    _HAS_CV2 = True
except Exception as e:
    cv2 = None
    print(f"[CVInput] OpenCV (cv2) nao esta instalado: {e}")

import numpy as np
import os
import threading
import time

# ── Localiza o modelo ─────────────────────────────────────────────────
_MODEL_PATH = os.path.join("assets", "models", "hand_landmarker.task")
if not os.path.exists(_MODEL_PATH):
    _MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "models", "hand_landmarker.task")
if not os.path.exists(_MODEL_PATH):
    _MODEL_PATH = os.path.join("game", "assets", "models", "hand_landmarker.task")
if not os.path.exists(_MODEL_PATH):
    _MODEL_PATH = None

_HAS_MEDIAPIPE = False
try:
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        HandLandmarker,
        HandLandmarkerOptions,
        HandLandmarkerResult,
        FaceDetector,
        FaceDetectorOptions,
    )
    from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
        VisionTaskRunningMode,
    )
    import mediapipe as mp
    _MP_IMAGE = mp.Image
    _MP_FORMAT = mp.ImageFormat
    _HAS_MEDIAPIPE = True
except Exception as e:
    print(f"[CVInput] mediapipe tasks vision import falhou: {e}")

_HAS_MODEL = _MODEL_PATH is not None and _HAS_MEDIAPIPE

if not _HAS_MODEL:
    print("[CVInput] Modelo hand_landmarker.task não encontrado ou MediaPipe indisponível.")
    print("[CVInput] Para habilitar o hand tracking de forma completa:")
    print("[CVInput]   wget -O hand_landmarker.task https://storage.googleapis.com/"
          "mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")


# ── Detecção de mão fechada por landmarks ─────────────────────────────

# Conexões do esqueleto da mão (MediaPipe)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Polegar
    (0, 5), (5, 6), (6, 7), (7, 8),        # Indicador
    (5, 9), (9, 10), (10, 11), (11, 12),   # Médio
    (9, 13), (13, 14), (14, 15), (15, 16), # Anelar
    (13, 17), (17, 18), (18, 19), (19, 20),# Mínimo
    (0, 17)                                # Palma da mão
]

def _is_hand_closed(landmarks) -> bool:
    """Retorna True se os 4 dedos (exceto polegar) estão fechados."""
    if len(landmarks) < 21:
        return False
    tips  = [8, 12, 16, 20]
    bases = [6, 10, 14, 18]
    return all(landmarks[t].y > landmarks[b].y for t, b in zip(tips, bases))


# ══════════════════════════════════════════════════════════════════════
# CVInput
# ══════════════════════════════════════════════════════════════════════

class CVInput:
    """
    Detecta posição da mão (normalizada 0-1) e estado fechado/aberto.
    Roda todo o processamento de câmera em uma thread de background
    para não engasgar a thread principal de renderização do Panda3D.
    """

    def __init__(self, cap=None):
        self.cap = cap
        self._enabled = False

        # Posição persistente normalizada
        self._nx: float = 0.5
        self._ny: float = 0.5
        self._nxs = [0.5, 0.5]
        self._nys = [0.5, 0.5]
        self.detected_hands = []
        self._prev_hand_lms = {}
        self._ever_detected = False
        self._currently_detected = False
        self._hand_closed   = False

        self._smoothing = 0.30

        # Câmera preview (bytes de imagem e metadados)
        self.preview_rgb_bytes: bytes | None = None
        self.preview_jpeg_bytes: bytes | None = None
        self.preview_w: int = 0
        self.preview_h: int = 0
        
        # Face / Head detector usando MediaPipe FaceDetector
        self._face_detector = None
        self._last_face = None
        self.face_x = None
        self.face_y = None
        self.face_detection_enabled = False

        # Pose landmarks tracking (lazy-loaded when enabled)
        self.pose_detection_enabled = False
        self.latest_pose_landmarks = None

        # Throttle counters (reduz carga de CPU sem perda perceptível de responsividade)
        self._pose_detect_counter: int = 0   # PoseLandmarker: 1 a cada 2 frames
        self._face_detect_counter_local: int = 0  # FaceDetector: já throttled internamente

        # Busca pelo arquivo de modelo face_detector.tflite
        face_path = os.path.join("assets", "models", "face_detector.tflite")
        if not os.path.exists(face_path):
            face_path = os.path.join(os.path.dirname(__file__), "..", "assets", "models", "face_detector.tflite")
        self._face_model_path = face_path if os.path.exists(face_path) else None

        if self._face_model_path and _HAS_MEDIAPIPE:
            try:
                options = FaceDetectorOptions(
                    base_options=BaseOptions(model_asset_path=self._face_model_path),
                    running_mode=VisionTaskRunningMode.IMAGE,
                    min_detection_confidence=0.5
                )
                self._face_detector = FaceDetector.create_from_options(options)
                print("[CVInput] FaceDetector (MediaPipe Tasks) iniciado com sucesso.")
            except Exception as e:
                print(f"[CVInput] Falha ao iniciar FaceDetector: {e}")

        self._lock = threading.Lock()
        self._running = True

        if _HAS_MODEL and cap is not None:
            self._init_landmarker()

        if cap is not None:
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

    def _init_landmarker(self):
        try:
            # Modo LIVE_STREAM (callback assíncrono)
            self._result_lock   = threading.Lock()
            self._latest_result: HandLandmarkerResult | None = None
            self._latest_ts     = 0

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_MODEL_PATH),
                running_mode=VisionTaskRunningMode.LIVE_STREAM,
                num_hands=2,
                min_hand_detection_confidence=0.65,
                min_hand_presence_confidence=0.50,
                min_tracking_confidence=0.50,
                result_callback=self._on_result,
            )
            self._landmarker = HandLandmarker.create_from_options(options)
            self._enabled    = True
            self._ts_ms      = 0
            print("[CVInput] HandLandmarker (tasks API) iniciado com sucesso.")
        except Exception as e:
            print(f"[CVInput] Falha ao iniciar HandLandmarker: {e}")
            self._enabled = False

    def _on_result(self, result: "HandLandmarkerResult", output_image, timestamp_ms: int):
        with self._result_lock:
            self._latest_result = result
            self._latest_ts     = timestamp_ms

    def _capture_loop(self):
        face_detect_counter = 0
        while self._running:
            if self.cap is None:
                time.sleep(0.03)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Espelha o frame horizontalmente para o feedback da câmera e coordenadas de controle do mediapipe
            frame = cv2.flip(frame, 1)

            face_x = None
            face_y = None
            last_face = None
            pose_landmarks = None
            local_hands = []
            nx, ny = self._nx, self._ny
            hand_closed = False
            ever_detected = self._ever_detected
            currently_detected = False

            # --- MODE 1: Pose Tracking (Penlinux minigame / body tracking) ---
            if self.pose_detection_enabled:
                # Lazy-init do PoseDetector (executado apenas uma vez dentro da thread da câmera)
                if not hasattr(self, "_pose_detector"):
                    try:
                        from mediapipe.tasks import python
                        from mediapipe.tasks.python import vision
                        import mediapipe as mp
                        
                        pose_path = os.path.join("assets", "models", "pose_landmarker_full.task")
                        if not os.path.exists(pose_path):
                            pose_path = os.path.join(os.path.dirname(__file__), "..", "assets", "models", "pose_landmarker_full.task")
                        
                        if os.path.exists(pose_path):
                            base_options = python.BaseOptions(model_asset_path=pose_path)
                            options = vision.PoseLandmarkerOptions(
                                base_options=base_options,
                                running_mode=vision.RunningMode.IMAGE,
                                num_poses=1,
                                min_pose_detection_confidence=0.5,
                                min_pose_presence_confidence=0.5,
                                min_tracking_confidence=0.5
                            )
                            self._pose_detector = vision.PoseLandmarker.create_from_options(options)
                            print("[CVInput] PoseLandmarker (Tasks API) iniciado com sucesso.")
                        else:
                            print(f"[CVInput] Modelo pose_landmarker_full.task nao encontrado.")
                            self._pose_detector = None
                    except Exception as e:
                        print(f"[CVInput] Falha ao iniciar PoseLandmarker options: {e}")
                        self._pose_detector = None

                if hasattr(self, "_pose_detector") and self._pose_detector is not None:
                    # Throttle: executa detecção de pose 1 a cada 2 frames (~15fps) para aliviar CPU
                    self._pose_detect_counter += 1
                    if self._pose_detect_counter % 2 == 0:
                        try:
                            import mediapipe as mp
                            rgb_pose = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_pose)
                            result = self._pose_detector.detect(mp_image)
                            if result and result.pose_landmarks:
                                pose_landmarks = result.pose_landmarks[0]
                                self.draw_custom_pose_landmarks(frame, pose_landmarks)
                        except Exception as e:
                            print(f"[CVInput] Erro no processamento do PoseLandmarker: {e}")
                    else:
                        # Reutiliza o resultado do frame anterior para manter fluidez visual
                        pose_landmarks = self.latest_pose_landmarks

            # --- MODE 2: Face / Head Tracking (Dodge minigame) ---
            elif self.face_detection_enabled and self._face_detector is not None:
                face_detect_counter += 1
                last_face = self._last_face
                if face_detect_counter % 3 == 0 or last_face is None:
                    try:
                        rgb_face = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        mp_image = _MP_IMAGE(image_format=_MP_FORMAT.SRGB, data=rgb_face)
                        result = self._face_detector.detect(mp_image)
                        if result and result.detections:
                            detection = result.detections[0]
                            bbox = detection.bounding_box
                            face_center_x = bbox.origin_x + bbox.width / 2.0
                            face_center_y = bbox.origin_y + bbox.height / 2.0
                            h_img, w_img, _ = frame.shape
                            face_x = face_center_x / w_img
                            face_y = face_center_y / h_img
                            
                            ox = int(bbox.origin_x)
                            oy = int(bbox.origin_y)
                            ow = int(bbox.width)
                            oh = int(bbox.height)
                            last_face = (ox, oy, ow, oh)
                        else:
                            face_x = None
                            face_y = None
                            last_face = None
                    except Exception as e:
                        print(f"[CVInput] Face detection error: {e}")
                else:
                    face_x = self.face_x
                    face_y = self.face_y

                if last_face is not None:
                    ox, oy, ow, oh = last_face
                    cv2.rectangle(frame, (ox, oy), (ox+ow, oy+oh), (0, 255, 0), 3)

            # --- MODE 3: Hand Tracking (Normal UI & Navigation) ---
            elif self._enabled:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = _MP_IMAGE(image_format=_MP_FORMAT.SRGB, data=rgb)

                self._ts_ms += 33   # ~30 fps timestamp
                try:
                    self._landmarker.detect_async(mp_img, self._ts_ms)
                except (OSError, Exception):
                    pass

                with self._result_lock:
                    result = self._latest_result

                if result and result.hand_landmarks:
                    ever_detected = True
                    currently_detected = True
                    try:
                        alpha = 0.45
                        for h_idx, lm in enumerate(result.hand_landmarks[:2]):
                            wrist = lm[0]
                            index = lm[8]

                            raw_x = wrist.x * 0.4 + index.x * 0.6
                            raw_y = wrist.y * 0.35 + index.y * 0.65

                            while len(self._nxs) <= h_idx:
                                self._nxs.append(0.5)
                                self._nys.append(0.5)

                            self._nxs[h_idx] += (raw_x - self._nxs[h_idx]) * self._smoothing
                            self._nys[h_idx] += (raw_y - self._nys[h_idx]) * self._smoothing
                            h_nx = max(0.0, min(1.0, self._nxs[h_idx]))
                            h_ny = max(0.0, min(1.0, self._nys[h_idx]))

                            h_closed = _is_hand_closed(lm)

                            # EMA smoothing for 21 3D landmarks
                            smoothed_lms = []
                            if h_idx not in self._prev_hand_lms:
                                self._prev_hand_lms[h_idx] = []

                            for pt_idx, p in enumerate(lm):
                                px, py, pz = p.x, p.y, p.z
                                if pt_idx < len(self._prev_hand_lms[h_idx]):
                                    prev_x, prev_y, prev_z = self._prev_hand_lms[h_idx][pt_idx]
                                    sx = alpha * px + (1.0 - alpha) * prev_x
                                    sy = alpha * py + (1.0 - alpha) * prev_y
                                    sz = alpha * pz + (1.0 - alpha) * prev_z
                                else:
                                    sx, sy, sz = px, py, pz
                                smoothed_lms.append((sx, sy, sz))
                            self._prev_hand_lms[h_idx] = smoothed_lms

                            # Check pinch (thumb tip #4 vs index tip #8)
                            thumb_tip = smoothed_lms[4]
                            index_tip = smoothed_lms[8]
                            pinch_dist = np.hypot(thumb_tip[0] - index_tip[0], thumb_tip[1] - index_tip[1])
                            is_pinched = pinch_dist < 0.055

                            local_hands.append({
                                "pos": (h_nx, h_ny),
                                "closed": h_closed,
                                "landmarks": smoothed_lms
                            })
                    except Exception as e:
                        print(f"[CVInput] Erro ao processar landmarks da mao: {e}")
                else:
                    hand_closed = False
                    currently_detected = False

            # Pré-converte para o formato RGB uma única vez (já espelhado e na vertical correta)
            rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_bytes = rgb_out.tobytes()
            h_f, w_f, _ = rgb_out.shape

            # Encode JPEG somente quando a webcam estiver visível (evita overhead desnecessário)
            jpeg_bytes = None

            # Atualiza variáveis compartilhadas com exclusão mútua
            with self._lock:
                self.preview_rgb_bytes = rgb_bytes
                self.preview_jpeg_bytes = jpeg_bytes
                self.preview_w = w_f
                self.preview_h = h_f
                self.face_x = face_x
                self.face_y = face_y
                self._last_face = last_face
                self.detected_hands = local_hands
                self.latest_pose_landmarks = pose_landmarks
                if local_hands:
                    self._nx = local_hands[0]["pos"][0]
                    self._ny = local_hands[0]["pos"][1]
                    self._hand_closed = local_hands[0]["closed"]
                    self._currently_detected = True
                    self._ever_detected = True
                else:
                    self._currently_detected = False
                    self._hand_closed = False

            # Sleep de 5ms: alivia spin de CPU sem impacto perceptível nos 30fps da câmera.
            # A câmera física bloqueia internamente no cap.read() por ~33ms (30fps), então
            # este sleep adicional só ocorre quando o loop termina antes do próximo frame.
            time.sleep(0.005)

    # ── API pública ───────────────────────────────────────────────────

    def get_hands_landmarks(self):
        with self._lock:
            return list(self.detected_hands)

    def update(self):
        """
        Retorna (finger_pos_norm, hand_closed).
        finger_pos_norm: (x, y) em [0,1] com origem top-left, ou None se nunca detectado.
        """
        if self.cap is None:
            return None, False

        with self._lock:
            nx, ny = self._nx, self._ny
            hand_closed = self._hand_closed
            currently_detected = getattr(self, "_currently_detected", False)

        if not currently_detected:
            return None, False

        return (nx, ny), hand_closed

    def get_head_position(self):
        """Standardized head landmark position (face_x, face_y) in [0.0, 1.0]."""
        with self._lock:
            fx = self.face_x if self.face_x is not None else 0.5
            fy = self.face_y if self.face_y is not None else 0.5
            return float(fx), float(fy)

    def draw_custom_pose_landmarks(self, frame, landmarks):
        h, w, _ = frame.shape
        connections = [
            (11, 12),  # Shoulder to shoulder
            (11, 13), (13, 15),  # Left arm
            (12, 14), (14, 16),  # Right arm
            (11, 23), (12, 24), (23, 24)  # Torso
        ]
        # Draw connections
        for start_idx, end_idx in connections:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                pt_start = landmarks[start_idx]
                pt_end = landmarks[end_idx]
                x_s = int(pt_start.x * w)
                y_s = int(pt_start.y * h)
                x_e = int(pt_end.x * w)
                y_e = int(pt_end.y * h)
                cv2.line(frame, (x_s, y_s), (x_e, y_e), (0, 236, 255), 3)

        # Draw glowing joint points
        for idx in [11, 12, 13, 14, 15, 16]:
            if idx < len(landmarks):
                pt = landmarks[idx]
                x_px = int(pt.x * w)
                y_px = int(pt.y * h)
                cv2.circle(frame, (x_px, y_px), 8, (35, 255, 120), -1)
                cv2.circle(frame, (x_px, y_px), 4, (255, 255, 255), -1)

    def release(self):
        self._running = False
        if self._enabled:
            try:
                self._landmarker.close()
            except Exception:
                pass
        if hasattr(self, "_face_detector") and self._face_detector:
            try:
                self._face_detector.close()
            except Exception:
                pass
        if hasattr(self, "_pose_detector") and self._pose_detector:
            try:
                self._pose_detector.close()
            except Exception:
                pass
        if self.cap is not None:
            self.cap.release()
