import cv2
import threading
import time
import math
from reachy_sdk.camera import ZoomLevel


class FaceTracker:

    MAX_FACE_COUNT = 5

    def __init__(self, reachyController, fps: float = 10.0, fovHDeg: float = 125.0, fovVDeg: float = 93.0):
        self._reachy = reachyController
        self._detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._fps = fps
        self._lock = threading.Lock()
        self._faceCenter = None
        self._running = False
        self._thread = None
        self._fovH = fovHDeg
        self._fovV = fovVDeg
        self.faceCount: int = 0
        self._reachy.head.setCameraZoomLevel(ZoomLevel.OUT)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def getFaceCenter(self) -> tuple | None:
        with self._lock:
            return self._faceCenter

    def _loop(self) -> None:
        interval = 1.0 / self._fps
        while self._running:
            t = time.time()
            frame = self._reachy.head.cameraLeft.last_frame
            if frame is None:
                self.faceCount -= 1
                if self.faceCount < 0:
                    self.faceCount = 0
                time.sleep(interval)
                continue
            self.faceCount += 1
            if self.faceCount < FaceTracker.MAX_FACE_COUNT:
                continue
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._detector.detectMultiScale(gray, 1.1, 5, minSize=(16, 16))
            if len(faces) > 0:
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                cxNorm = ((x + fw / 2) / w - 0.5) * 2
                cyNorm = ((y + fh / 2) / h - 0.5) * 2
                with self._lock:
                    self._faceCenter = (cxNorm, cyNorm)
            else:
                with self._lock:
                    self._faceCenter = None
            time.sleep(max(0, interval - (time.time() - t)))

    def getLookAtTarget(self) -> list | None:
        face = self.getFaceCenter()
        if face is None:
            return None
        return self._faceToLookAt(face[0], face[1])

    def _faceToLookAt(self, cxNorm: float, cyNorm: float, distance: float = 1.0) -> list:
        angleH = cxNorm * (self._fovH / 2)
        angleV = -cyNorm * (self._fovV / 2)
        x = distance * math.cos(math.radians(angleV)) * math.cos(math.radians(angleH))
        y = -distance * math.sin(math.radians(angleH))
        z = distance * math.sin(math.radians(angleV))
        return [round(x, 3), round(y, 3), round(z, 3)]