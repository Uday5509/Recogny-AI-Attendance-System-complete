"""Local face detection (YuNet) + embeddings (SFace) via OpenCV DNN."""
import os
import threading
import urllib.request
import numpy as np
import cv2

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
DET_FILE = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
REC_FILE = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")
BASE = "https://github.com/opencv/opencv_zoo/raw/main/models/"
URLS = {
    DET_FILE: BASE + "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    REC_FILE: BASE + "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

_lock = threading.Lock()
_detector = None
_recognizer = None


def _ensure_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for path, url in URLS.items():
        if os.path.exists(path) and os.path.getsize(path) > 100_000:
            continue
        print(f"Downloading model {os.path.basename(path)} ...")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as exc:
            if os.path.exists(path):
                os.remove(path)
            raise RuntimeError(
                f"Could not download {os.path.basename(path)} ({exc}). Download it manually from\n"
                f"{url}\nand save it in the 'models' folder."
            )


def _load():
    global _detector, _recognizer
    if _detector is None:
        _ensure_models()
        _detector = cv2.FaceDetectorYN.create(DET_FILE, "", (320, 320), 0.8, 0.3, 5000)
        _recognizer = cv2.FaceRecognizerSF.create(REC_FILE, "")


def decode_image(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def get_embedding(img):
    """Return a 128-d float32 embedding of the largest face, or None if no face."""
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = 1024 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]
    with _lock:
        _load()
        _detector.setInputSize((w, h))
        _, faces = _detector.detect(img)
        if faces is None or len(faces) == 0:
            return None
        face = max(faces, key=lambda f: f[2] * f[3])
        feat = _recognizer.feature(_recognizer.alignCrop(img, face))
    return np.asarray(feat, dtype=np.float32).flatten()


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def best_match(embedding, candidates):
    """candidates: iterable of (row, embedding). Returns (row, score) with highest score."""
    best, best_score = None, -1.0
    for row, emb in candidates:
        s = cosine(embedding, emb)
        if s > best_score:
            best, best_score = row, s
    return best, best_score
