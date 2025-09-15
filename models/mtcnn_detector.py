import cv2
import numpy as np
import base64
from mtcnn import MTCNN

class MTCNNDetector:

    def __init__(self, min_confidence: float = 0.90, draw_landmarks: bool = True):
        self.detector = MTCNN()
        self.min_confidence = float(min_confidence)
        self.draw_landmarks = bool(draw_landmarks)

    def detect_faces(self, img: np.ndarray, return_annotated: bool = True):
        if img is None or not isinstance(img, np.ndarray):
            raise ValueError("image must be a valid OpenCV BGR numpy array")

        annotated = img.copy() if return_annotated else None
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        raw_faces = self.detector.detect_faces(rgb)
        faces = [f for f in raw_faces if f.get("confidence", 0.0) >= self.min_confidence]

        extracted = []
        for i, f in enumerate(faces):
            x, y, w, h = f.get("box", (0,0,0,0))
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = max(0, int(x + w))
            y2 = max(0, int(y + h))

            face_img = img[y1:y2, x1:x2]
            if face_img.size == 0:
                continue

            extracted.append(face_img)

            if annotated is not None:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
                conf = f.get("confidence", 0.0)
                cv2.putText(
                    annotated,
                    f"{conf:.2f}",
                    (x1, max(10, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                if self.draw_landmarks:
                    keypoints = f.get("keypoints", {})
                    for k, pt in keypoints.items():
                        px, py = int(pt[0]), int(pt[1])
                        cv2.circle(annotated, (px, py), 2, (0, 255, 0), 2)

        return extracted, annotated if return_annotated else None

    @staticmethod
    def to_base64(img: np.ndarray) -> str:
        """Convert OpenCV BGR image to base64 PNG string."""
        if img is None or not isinstance(img, np.ndarray):
            raise ValueError("`img` must be a valid numpy array")
        success, buff = cv2.imencode(".png", img)
        if not success:
            raise RuntimeError("Failed to encode image")
        return base64.b64encode(buff).decode("utf-8")
