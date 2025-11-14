import os
import base64
import cv2
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    from insightface.app import FaceAnalysis
except ImportError:
    FaceAnalysis = None


def _log(msg: str):
    print(f"[ArcFace] {msg}")


class ArcFaceRecognizer:
    def __init__(
        self,
        model_name: str = "buffalo_l",
        providers: Optional[List[str]] = None,
        det_size: Tuple[int, int] = (640, 640),
        det_thresh: float = 0.5
    ):
        if FaceAnalysis is None:
            raise ImportError(
                "insightface is not installed"
            )
        
        # This line is critical for Hugging Face Spaces
        os.environ['INSIGHTFACE_HOME'] = './.insightface_cache'

        if providers is None:
            providers = ["CPUExecutionProvider"]

        self.app = FaceAnalysis(name=model_name, providers=providers)
        
        # Pass all hyperparameters to the model's prepare function
        self.app.prepare(
            ctx_id=0, 
            det_size=det_size, 
            det_thresh=det_thresh 
        )
        
        _log(f"Initialized model '{model_name}' (det_size={det_size}, det_thresh={det_thresh})")

    def recognize_from_enrolled(
        self,
        img: np.ndarray,
        enrolled: Dict[str, np.ndarray],
        threshold: float = 0.3, # This is the "recognition_thresh"
    ) -> Dict[str, object]:
        
        if img is None or not hasattr(img, "shape"):
            raise ValueError("img must be a valid numpy image array")

        # Normalize the enrolled vectors
        norm_enrolled: Dict[str, np.ndarray] = {}
        for sid, vec in enrolled.items():
            v = np.asarray(vec, dtype=np.float32).reshape(-1)
            n = float(np.linalg.norm(v))
            if n > 0:
                v = v / n
            norm_enrolled[str(sid)] = v

        faces = self.app.get(img) 
        total_faces_detected = len(faces)
        recognized_faces_count = 0
        best_scores: Dict[str, float] = {}
        
        unknown_faces_base64: List[str] = []

        for face in faces:
            q = face.normed_embedding.astype(np.float32)
            best_sid = None
            best_sim = -1.0
            
            # Find best student match for this face
            for sid, ref in norm_enrolled.items():
                sim = float(np.dot(q, ref))
                if sim > best_sim:
                    best_sim = sim
                    best_sid = sid
            
            # Check if this face is a match
            if best_sid is not None and best_sim >= threshold:
                recognized_faces_count += 1
                prev = best_scores.get(best_sid, -1.0)
                if best_sim > prev:
                    best_scores[best_sid] = best_sim
            else:
                try:
                    x1, y1, x2, y2 = map(int, face.bbox)
                    padding = 10
                    h, w, _ = img.shape
                    x1 = max(0, x1 - padding)
                    y1 = max(0, y1 - padding)
                    x2 = min(w, x2 + padding)
                    y2 = min(h, y2 + padding)
                    
                    cropped_img = img[y1:y2, x1:x2]
                    
                    if cropped_img.size > 0:
                        _, buffer = cv2.imencode('.jpg', cropped_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                        b64_string = base64.b64encode(buffer).decode('utf-8')
                        unknown_faces_base64.append(b64_string)
                except Exception as e:
                    _log(f"WARN: Could not crop or encode unknown face: {e}")


        present_students = list(best_scores.keys())
        confidence_scores = {sid: float(score) for sid, score in best_scores.items()}
        coverage = (recognized_faces_count / total_faces_detected) if total_faces_detected > 0 else 0.0

        return {
            "present_students": sorted(present_students),
            "confidence_scores": confidence_scores,
            "metrics": {
                "total_faces_detected": total_faces_detected,
                "recognized_faces_count": recognized_faces_count,
                "coverage": coverage,
                "threshold_used": threshold
            },
            "unknown_faces": unknown_faces_base64
        }
    
def _decode_base64_image_to_bgr(data: str) -> np.ndarray:
    if not isinstance(data, str) or not data:
        raise ValueError("class_image must be a non-empty base64-encoded string")
    if "," in data and data.lower().startswith("data:"):
        data = data.split(",", 1)[1]
    
    try:
        raw = base64.b64decode(data)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image (cv2.imdecode returned None)")
        return img
    except Exception as e:
        _log(f"Base64 decode error: {e}")
        raise ValueError(f"Failed to decode image from base64 bytes: {e}")