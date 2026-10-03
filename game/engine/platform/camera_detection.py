# engine/platform/camera_detection.py — detecção de dispositivos de captura (câmera)

def detect_camera_index() -> int:
    try:
        from settings import CAMERA_INDEX
        if CAMERA_INDEX is not None:
            print(f"[camera_detection.py] Bypassing automatic camera detection, forcing index: {CAMERA_INDEX}")
            return CAMERA_INDEX
    except Exception as e:
        print(f"[camera_detection.py] Error checking settings.CAMERA_INDEX: {e}")

    try:
        import cv2
    except ImportError:
        print("[camera_detection.py] OpenCV (cv2) not installed. Defaulting to camera 0.")
        return 0

    import sys
    # Detect first working camera
    for i in range(4):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(i, backend)
        if cap is not None:
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    cap.release()
                    print(f"[camera_detection.py] Automatically detected working camera at index: {i}")
                    return i
                cap.release()
    print("[camera_detection.py] No working camera detected. Defaulting to index 0.")
    return 0
