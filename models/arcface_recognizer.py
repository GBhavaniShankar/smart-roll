import os
import cv2
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

"""
ArcFace (InsightFace) based facial recognition utility.

Features:
1. Build an embeddings database from a directory of known faces (supports:
   - flat directory:  student1.jpg, alice.png, bob_1.jpg ... (name from filename)
   - hierarchical:    root/person_name/image1.jpg (name from folder)
2. Recognize faces in a single target image against the database.
3. Optionally annotate and save the output image.
4. Clean ArcFace-only implementation (no MTCNN dependency).

Dependencies (install first):
    pip install insightface onnxruntime opencv-python

IMPORTANT: ArcFace expects aligned 112x112 RGB faces. The InsightFace `FaceAnalysis` pipeline
handles detection + alignment internally. The default pipeline uses InsightFace's own detector
for best results (no external cropper needed).
"""

try:
    from insightface.app import FaceAnalysis  # type: ignore
except ImportError:
    FaceAnalysis = None  # runtime check later


def _log(msg: str):
    print(f"[ArcFace] {msg}")


class ArcFaceRecognizer:
    def __init__(
        self,
        model_name: str = "buffalo_l",
        providers: Optional[List[str]] = None,
        det_size: Tuple[int, int] = (640, 640),
    ):
        """Initialize ArcFace / InsightFace pipeline.

        model_name: One of the model packs shipped with InsightFace (buffalo_l, antelopev2, etc.)
        providers: ONNXRuntime execution providers. Default: CPU only.
        det_size:   Detection size (width,height) for FaceAnalysis.prepare.
        """
        if FaceAnalysis is None:
            raise ImportError(
                "insightface is not installed. Run: pip install insightface onnxruntime"
            )
        if providers is None:
            providers = ["CPUExecutionProvider"]  # For Windows without GPU config

        self.app = FaceAnalysis(name=model_name, providers=providers)
        # On CPU-only environments, ctx_id can be -1; with providers set, 0 works as well.
        self.app.prepare(ctx_id=0, det_size=det_size)
        _log(f"Initialized model '{model_name}' with providers={providers} det_size={det_size}")

    # ------------------------------------------------------------------
    # Embedding DB BUILD / LOAD / SAVE
    # ------------------------------------------------------------------
    @staticmethod
    def _collect_image_paths(root_dir: str) -> List[Path]:
        exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        paths: List[Path] = []
        root = Path(root_dir)
        if not root.exists():
            raise FileNotFoundError(f"Directory not found: {root_dir}")
        for pattern in exts:
            paths.extend(root.rglob(pattern))  # supports nested folders
        return paths

    @staticmethod
    def _name_from_path(path: Path, hierarchical: bool) -> str:
        if hierarchical:
            return path.parent.name  # folder name is identity
        return path.stem  # filename (without extension) is identity

    def build_embeddings_db(
        self,
        faces_dir: str,
        db_path: str = "arcface_embeddings.pkl",
        hierarchical: bool = True,
        min_face: int = 40,
        max_images_per_identity: Optional[int] = None,
    ) -> Dict[str, List[np.ndarray]]:
        """Build (or rebuild) an embeddings database.

        faces_dir: directory containing known faces.
            hierarchical=True expects faces_dir/identity/imageXX.jpg.
            hierarchical=False expects faces directly inside faces_dir.
        db_path: pickle output.
        min_face: minimum face width or height accepted (skip tiny detections).
        max_images_per_identity: optionally cap number of images per identity to reduce DB size.
        Returns: mapping identity -> list of 512-d normalized embeddings.
        """
        paths = self._collect_image_paths(faces_dir)
        if not paths:
            raise RuntimeError(f"No images found in {faces_dir}")
        _log(f"Found {len(paths)} candidate images under '{faces_dir}'")

        db: Dict[str, List[np.ndarray]] = {}
        for p in paths:
            name = self._name_from_path(p, hierarchical)
            if max_images_per_identity and name in db and len(db[name]) >= max_images_per_identity:
                continue
            img = cv2.imread(str(p))
            if img is None:
                _log(f"WARN: Could not read {p}")
                continue
            faces = self.app.get(img)
            if not faces:
                _log(f"WARN: No face in {p}")
                continue
            # choose largest face
            face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
            w = face.bbox[2]
            h = face.bbox[3]
            if w < min_face or h < min_face:
                _log(f"SKIP tiny face ({w}x{h}) in {p}")
                continue
            emb = face.normed_embedding  # already L2 normalized
            db.setdefault(name, []).append(emb.astype(np.float32))
        if not db:
            raise RuntimeError("Database empty: no usable faces.")

        with open(db_path, "wb") as f:
            pickle.dump(db, f)
        _log(f"Saved embeddings DB with {len(db)} identities to {db_path}")
        return db

    @staticmethod
    def load_db(db_path: str) -> Dict[str, List[np.ndarray]]:
        with open(db_path, "rb") as f:
            db = pickle.load(f)
        # ensure numpy arrays float32
        for k, lst in db.items():
            db[k] = [np.asarray(v, dtype=np.float32) for v in lst]
        return db

    # ------------------------------------------------------------------
    # RECOGNITION
    # ------------------------------------------------------------------
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        # embeddings from insightface should already be L2 normalized; dot is cosine
        return float(np.dot(a, b))

    def _best_match(
        self,
        query_emb: np.ndarray,
        db: Dict[str, List[np.ndarray]],
        threshold: float,
    ) -> Tuple[str, float]:
        best_name = "UNKNOWN"
        best_score = -1.0
        for name, embs in db.items():
            # compute max similarity across that identity's embeddings
            sim = max(self._cosine_similarity(query_emb, e) for e in embs)
            if sim > best_score:
                best_score = sim
                best_name = name
        if best_score < threshold:
            return "UNKNOWN", best_score
        return best_name, best_score

    def recognize_image(
        self,
        image_path: str,
        db_path: str,
        output_annotated: Optional[str] = None,
        threshold: float = 0.35,
        min_size: int = 0,
        mapping: Optional[Dict[str, str]] = None,
        unique: bool = False,
    ) -> List[dict]:
        """Recognize faces in a single image.

        threshold: typical cosine similarity threshold ranges roughly 0.3~0.5 depending on model
                   and intra-class variation. Start ~0.35 (higher = stricter).
        Returns list of dicts: [{'bbox':(x1,y1,x2,y2),'identity':str,'score':float,'raw_similarity':float}]
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Embeddings DB not found: {db_path}")
        db = self.load_db(db_path)
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        faces = self.app.get(img)
        # optionally filter tiny faces
        filtered_faces = []
        for face in faces:
            x1, y1, x2, y2 = map(int, face.bbox)
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            if min_size and (w < min_size or h < min_size):
                continue
            filtered_faces.append(face)

        results: List[dict] = []
        for face in filtered_faces:
            emb = face.normed_embedding.astype(np.float32)
            name, sim = self._best_match(emb, db, threshold)
            x1, y1, x2, y2 = map(int, face.bbox)
            label_name = name
            if mapping and name in mapping:
                label_name = mapping[name]
            results.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "identity": label_name,
                    "similarity": sim,
                }
            )
        # If unique mode, keep only the best occurrence per identity (excluding UNKNOWN)
        if unique and results:
            best_per_identity: Dict[str, Tuple[int, float]] = {}
            for idx, r in enumerate(results):
                name = r["identity"]
                if name == "UNKNOWN":
                    continue
                sim = r["similarity"]
                if name not in best_per_identity or sim > best_per_identity[name][1]:
                    best_per_identity[name] = (idx, sim)
            keep_indices = {idx for idx, _ in best_per_identity.values()}
            results = [r for i, r in enumerate(results) if (r["identity"] == "UNKNOWN") or (i in keep_indices)]

        # Draw annotations if requested
        if output_annotated:
            for r in results:
                x1, y1, x2, y2 = r["bbox"]
                name = r["identity"]
                sim = r["similarity"]
                color = (0, 255, 0) if name != "UNKNOWN" else (0, 0, 255)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                label = f"{name}:{sim:.2f}" if name != "UNKNOWN" else f"UNKNOWN:{sim:.2f}"
                cv2.putText(
                    img,
                    label,
                    (x1, y1 - 5 if y1 - 5 > 10 else y1 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )
        if output_annotated:
            out_dir = os.path.dirname(output_annotated)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated, img)
            _log(f"Annotated image saved to {output_annotated}")
        return results

    # (MTCNN-based crop recognition removed; ArcFace pipeline handles detection+alignment.)


def _default_db_path() -> str:
    return "arcface_embeddings.pkl"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ArcFace Recognition Utility")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Build embeddings DB from known faces directory")
    b.add_argument("faces_dir", help="Directory of known faces (flat or hierarchical)")
    b.add_argument("--db", default=_default_db_path())
    b.add_argument("--flat", action="store_true", help="Faces directory is flat (names from filenames)")
    b.add_argument("--max-per-id", type=int, default=None)

    r = sub.add_parser("recognize", help="Recognize faces in a single image")
    r.add_argument("image", help="Image path to recognize")
    r.add_argument("--db", default=_default_db_path())
    r.add_argument("--out", default=None, help="Optional annotated output image path")
    r.add_argument("--threshold", type=float, default=0.35)
    r.add_argument("--min-size", type=int, default=0, help="Minimum face size (pixels) to consider")
    r.add_argument("--map", dest="map_path", default=None, help="Optional JSON mapping: id->label for display")
    r.add_argument("--unique", action="store_true", help="Annotate only the best match per identity")

    args = parser.parse_args()

    recognizer = ArcFaceRecognizer()
    if args.command == "build":
        recognizer.build_embeddings_db(
            faces_dir=args.faces_dir,
            db_path=args.db,
            hierarchical=not args.flat,
            max_images_per_identity=args.max_per_id,
        )
    elif args.command == "recognize":
        # optional mapping for nicer labels
        mapping: Optional[Dict[str, str]] = None
        if args.map_path:
            import json
            if not os.path.exists(args.map_path):
                raise FileNotFoundError(f"Mapping file not found: {args.map_path}")
            with open(args.map_path, "r", encoding="utf-8") as f:
                raw_map = json.load(f)
            # Normalize mapping to str->str
            mapping = {}
            for k, v in raw_map.items():
                if isinstance(v, dict):
                    name = v.get("name")
                    roll = v.get("roll")
                    if name and roll:
                        mapping[str(k)] = f"{name} ({roll})"
                    elif name:
                        mapping[str(k)] = str(name)
                    else:
                        mapping[str(k)] = str(v)
                else:
                    mapping[str(k)] = str(v)
        results = recognizer.recognize_image(
            image_path=args.image,
            db_path=args.db,
            output_annotated=args.out,
            threshold=args.threshold,
            min_size=args.min_size,
            mapping=mapping,
            unique=args.unique,
        )
        _log("Results:")
        for r_ in results:
            _log(str(r_))
        if not results:
            _log("No faces found in image.")


if __name__ == "__main__":
    main()
