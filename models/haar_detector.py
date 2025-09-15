import cv2
import numpy as np
import base64
import os

class HaarDetector:
    def __init__(self):
        # Load from OpenCV's built-in haarcascades directory
        model_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Haar model not found at {model_path}")
        
        self.face_cascade = cv2.CascadeClassifier(model_path)

    def detect_faces(self, img: np.ndarray, return_annotated: bool = True):
        """Detect faces in an image and return cropped faces + optional annotated image."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(50, 50)
        )

        extracted_faces = []
        annotated_img = img.copy()

        for (x, y, w, h) in faces:
            face_roi = img[y:y+h, x:x+w]
            extracted_faces.append(face_roi)
            if return_annotated:
                cv2.rectangle(annotated_img, (x, y), (x+w, y+h), (0, 255, 0), 3)

        return extracted_faces, annotated_img if return_annotated else None

    @staticmethod
    def to_base64(img: np.ndarray) -> str:
        """Convert OpenCV image to base64 string."""
        _, buffer = cv2.imencode(".png", img)
        return base64.b64encode(buffer).decode("utf-8")
