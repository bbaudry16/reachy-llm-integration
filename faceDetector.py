import cv2
import threading
import time
from libs.reachyController import ReachyController
from reachy_sdk.camera import ZoomLevel
import math

class FaceTracker:

    def __init__(self, reachyController : "ReachyController", fps: float = 10.0,fov_h_deg: float = 125.0, fov_v_deg: float = 93.0, zoomLevel : "ZoomLevel" = ZoomLevel.OUT):
        self._reachy = reachyController
        self._detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._fps = fps
        self._lock = threading.Lock()
        self._faceCenter = None
        self._running = False
        self._thread = None
        self._fov_h = fov_h_deg
        self._fov_v = fov_v_deg

        self._reachy.head.setCameraZoomLevel(ZoomLevel.OUT)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def get_face_center(self):
        with self._lock:
            return self._faceCenter

    def _loop(self):
        interval = 1.0 / self._fps
        while self._running:
            t = time.time()

            frame = self._reachy.head.cameraLeft.last_frame
            if frame is None:
                time.sleep(interval)
                continue

            h, w = frame.shape[:2]
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._detector.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

            #take only the closest head
            if len(faces) > 0:
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                cx_norm = ((x + fw / 2) / w - 0.5) * 2
                cy_norm = ((y + fh / 2) / h - 0.5) * 2
                with self._lock:
                    self._faceCenter = (cx_norm, cy_norm)
            else:
                with self._lock:
                    self._faceCenter = None

            time.sleep(max(0, interval - (time.time() - t)))
    
    def get_look_at_target(self) -> list | None:
        face = self.get_face_center()
        if face is None:
            return None
        return self.face_to_look_at(face[0], face[1], fov_h_deg=self._fov_h, fov_v_deg=self._fov_v)

    
    @staticmethod
    def face_to_look_at(cx_norm: float, cy_norm: float, distance: float = 1.0, fov_h_deg: float = 60.0, fov_v_deg: float = 45.0) -> list:
        angle_h = cx_norm * (fov_h_deg / 2)
        angle_v = -cy_norm * (fov_v_deg / 2)
        x = distance * math.cos(math.radians(angle_v)) * math.cos(math.radians(angle_h))
        y = -distance * math.sin(math.radians(angle_h))  # ← signe inversé
        z = distance * math.sin(math.radians(angle_v))
        return [round(x, 3), round(y, 3), round(z, 3)]