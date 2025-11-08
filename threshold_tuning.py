import os
import time
import json
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import wandb

from models.arcface_recognizer import ArcFaceRecognizer


def ensure_dir(p: str):
    if p:
        os.makedirs(p, exist_ok=True)


def find_images(images_dir: str, exts=("*.jpg", "*.jpeg", "*.png", "*.bmp")) -> List[Path]:
    d = Path(images_dir)
    files: List[Path] = []
    for pat in exts:
        files.extend(sorted(d.glob(pat)))
    return files


def run_once(recognizer: ArcFaceRecognizer, image_path: str, db_path: str, threshold: float) -> Dict:
    start = time.time()
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)

    t0 = time.time()
    faces = recognizer.app.get(img)
    det_ms = (time.time() - t0) * 1000.0

    # load DB
    db = recognizer.load_db(db_path)

    recognized = 0
    sims: List[float] = []

    for f in faces:
        emb = f.normed_embedding.astype(np.float32)
        name, sim = recognizer._best_match(emb, db, threshold)
        sims.append(float(sim))
        if name != "UNKNOWN":
            recognized += 1

    total_faces = len(faces)
    coverage = (recognized / total_faces) if total_faces > 0 else 0.0

    end = time.time()
    return {
        "total_faces": total_faces,
        "recognized": recognized,
        "coverage": coverage,
        "unknown_rate": 1.0 - coverage,
        "mean_similarity": float(np.mean(sims)) if sims else 0.0,
        "median_similarity": float(np.median(sims)) if sims else 0.0,
        "threshold": threshold,
        "det_ms": det_ms,
        "total_ms": (end - start) * 1000.0,
        "image": image_path,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Threshold tuning for ArcFace (logs to W&B)")
    parser.add_argument("images_dir", help="Directory with class photos for validation")
    parser.add_argument("--db", dest="db", default="arcface_embeddings.pkl", help="Embeddings DB path")
    parser.add_argument("--project", default="class-attendance", help="W&B project name")
    parser.add_argument("--entity", default=None, help="W&B entity/team (optional, else env WANDB_ENTITY)")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack name")
    args = parser.parse_args()

    thresholds = [0.1, 0.2, 0.3]

    images = find_images(args.images_dir)
    if not images:
        raise RuntimeError(f"No images found under {args.images_dir}")

    # Single recognizer per run (faster)
    recognizer = ArcFaceRecognizer(model_name=args.model)

    for thr in thresholds:
        run = wandb.init(
            project=args.project,
            entity=args.entity,
            config={
                "threshold": thr,
                "model": args.model,
                "db_path": args.db,
                "images_dir": args.images_dir,
            },
            reinit=True,
            name=f"thr_{thr:.2f}",
        )

        agg: Dict[str, float] = {"coverage": 0.0, "mean_similarity": 0.0, "unknown_rate": 0.0, "det_ms": 0.0, "total_ms": 0.0}
        count = 0

        for img_path in images:
            metrics = run_once(recognizer, str(img_path), args.db, thr)
            wandb.log(metrics)

            # aggregate simple means
            agg["coverage"] += metrics["coverage"]
            agg["mean_similarity"] += metrics["mean_similarity"]
            agg["unknown_rate"] += metrics["unknown_rate"]
            agg["det_ms"] += metrics["det_ms"]
            agg["total_ms"] += metrics["total_ms"]
            count += 1

        if count:
            for k in list(agg.keys()):
                agg[k] /= count
            wandb.summary.update({f"avg_{k}": v for k, v in agg.items()})

        run.finish()


if __name__ == "__main__":
    main()
