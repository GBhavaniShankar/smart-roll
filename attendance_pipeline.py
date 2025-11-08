import os
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

import cv2
import numpy as np

from models.arcface_recognizer import ArcFaceRecognizer


def ensure_dir(p: str):
    if p:
        os.makedirs(p, exist_ok=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_attendance_csv(csv_path: str, rows: List[Dict[str, str]]):
    ensure_dir(os.path.dirname(csv_path))
    header = ["timestamp", "image", "student_id", "similarity", "bbox", "status"]
    exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def write_attendance_csv_full(csv_path: str, rows: List[Dict[str, str]]):
    """Extended CSV with roll and name columns."""
    ensure_dir(os.path.dirname(csv_path))
    header = [
        "timestamp",
        "image",
        "student_id",
        "roll",
        "name",
        "similarity",
        "bbox",
        "status",
    ]
    exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def save_json(path: str, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_wandb(
    enabled: bool,
    project: str,
    run_name: str,
    config: dict,
    metrics: dict,
    annotated_img_path: Optional[str],
    predictions: List[dict],
    db_path: Optional[str] = None,
):
    if not enabled:
        return
    try:
        import wandb  # type: ignore
    except Exception as e:
        print(f"[wandb] Not logging (import failed): {e}")
        return

    wandb.init(project=project, name=run_name, config=config)
    wandb.log(metrics)

    # Log annotated image
    if annotated_img_path and os.path.exists(annotated_img_path):
        img = wandb.Image(annotated_img_path, caption=f"Annotated {Path(annotated_img_path).name}")
        wandb.log({"annotated": img})

    # Log predictions table
    if predictions:
        columns = ["identity", "name", "roll", "similarity", "bbox", "status"]
        data = [[
            p.get("identity"),
            p.get("mapped_name"),
            p.get("mapped_roll"),
            float(p.get("similarity", 0.0)),
            str(p.get("bbox")),
            p.get("status"),
        ] for p in predictions]
        table = wandb.Table(columns=columns, data=data)
        wandb.log({"predictions": table})

    # Register the embeddings DB as an artifact for traceability
    if db_path and os.path.exists(db_path):
        art = wandb.Artifact("arcface_embeddings", type="embeddings-db")
        art.add_file(db_path)
        wandb.log_artifact(art)

    wandb.finish()


def recognize_class_image(
    image_path: str,
    db_path: str,
    output_root: str = "recognition_outputs",
    threshold: float = 0.35,
    save_crops: bool = True,
    wandb_enable: bool = False,
    wandb_project: str = "face-attendance",
    model_name: str = "buffalo_l",
    student_map: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Run detection+recognition on a class photo and persist outputs + metrics.

    Returns a dict with summary, metrics, and paths.
    """
    recognizer = ArcFaceRecognizer(model_name=model_name)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Embeddings DB not found: {db_path}. Build it first using arcface_recognition.py build ...")

    db = recognizer.load_db(db_path)

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # Detect+embed using InsightFace (handles alignment)
    faces = recognizer.app.get(img)

    ts = now_stamp()
    run_dir = os.path.join(output_root, ts)
    crops_dir = os.path.join(run_dir, "crops")
    ensure_dir(run_dir)
    if save_crops:
        ensure_dir(crops_dir)

    annotated = img.copy()
    predictions: List[dict] = []
    recognized_count = 0
    similarities: List[float] = []

    for idx, face in enumerate(faces):
        emb = face.normed_embedding.astype(np.float32)
        name, sim = recognizer._best_match(emb, db, threshold)
        x1, y1, x2, y2 = map(int, face.bbox)
        status = "recognized" if name != "UNKNOWN" else "unknown"
        if status == "recognized":
            recognized_count += 1
            similarities.append(sim)

        # Build display label using student_map if available
        mapped_name = None
        mapped_roll = None
        if status == "recognized" and student_map is not None:
            info = student_map.get(str(name))
            if isinstance(info, dict):
                mapped_name = info.get("name")
                mapped_roll = info.get("roll")

        color = (0, 255, 0) if status == "recognized" else (0, 0, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        if status == "recognized" and mapped_name:
            label = f"{mapped_name} ({mapped_roll}) : {sim:.2f}"
        elif status == "recognized":
            label = f"{name}:{sim:.2f}"
        else:
            label = f"UNKNOWN:{sim:.2f}"
        cv2.putText(annotated, label, (x1, max(10, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        if save_crops:
            crop = img[max(0, y1):y2, max(0, x1):x2]
            if crop.size > 0:
                crop_path = os.path.join(crops_dir, f"face_{idx+1}_{name}.jpg")
                cv2.imwrite(crop_path, crop)
        else:
            crop_path = None

        predictions.append(
            {
                "identity": name,
                "similarity": float(sim),
                "bbox": [x1, y1, x2, y2],
                "status": status,
                "crop": crop_path,
                "mapped_name": mapped_name,
                "mapped_roll": mapped_roll,
            }
        )

    annotated_path = os.path.join(run_dir, f"{Path(image_path).stem}_annotated.jpg")
    cv2.imwrite(annotated_path, annotated)

    total_faces = len(faces)
    coverage = (recognized_count / total_faces) if total_faces > 0 else 0.0
    mean_sim = float(np.mean(similarities)) if similarities else 0.0
    median_sim = float(np.median(similarities)) if similarities else 0.0
    unknown_rate = 1.0 - coverage

    # A simple unlabeled selection score: prioritize recognizing more faces with strong confidence
    # You can tune weights per your preference.
    score = coverage * mean_sim

    metrics = {
        "total_faces": total_faces,
        "recognized": recognized_count,
        "coverage": coverage,
        "unknown_rate": unknown_rate,
        "mean_similarity": mean_sim,
        "median_similarity": median_sim,
        "score": score,
        "threshold": threshold,
    }

    # Persist prediction JSON for traceability
    meta = {
        "image": image_path,
        "timestamp": ts,
        "predictions": predictions,
        "metrics": metrics,
    }
    save_json(os.path.join(run_dir, "predictions.json"), meta)

    # Append attendance CSV (only recognized students)
    attendance_rows = []
    for p in predictions:
        if p["identity"] != "UNKNOWN":
            attendance_rows.append(
                {
                    "timestamp": ts,
                    "image": image_path,
                    "student_id": p["identity"],
                    "similarity": f"{p['similarity']:.4f}",
                    "bbox": str(tuple(p["bbox"])),
                    "status": p["status"],
                }
            )
    write_attendance_csv(os.path.join(output_root, "attendance_report.csv"), attendance_rows)

    # Optional: log to W&B
    log_wandb(
        enabled=wandb_enable,
        project=wandb_project,
        run_name=f"attendance_{ts}",
        config={
            "model": model_name,
            "db_path": db_path,
            "threshold": threshold,
        },
        metrics=metrics,
        annotated_img_path=annotated_path,
        predictions=predictions,
        db_path=db_path,
    )

    return {
        "run_dir": run_dir,
        "annotated": annotated_path,
        "metrics": metrics,
        "attendance_rows": attendance_rows,
    }


def maybe_build_db_if_missing(
    db_path: str,
    students_dir: Optional[str],
    hierarchical: bool = True,
    max_per_id: Optional[int] = None,
    model_name: str = "buffalo_l",
) -> str:
    if os.path.exists(db_path):
        return db_path
    if not students_dir:
        raise FileNotFoundError(
            f"Embeddings DB '{db_path}' not found and no students_dir provided to build it."
        )
    print(f"[build-db] Building embeddings DB from {students_dir} -> {db_path}")
    recognizer = ArcFaceRecognizer(model_name=model_name)
    recognizer.build_embeddings_db(
        faces_dir=students_dir,
        db_path=db_path,
        hierarchical=hierarchical,
        max_images_per_identity=max_per_id,
    )
    return db_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Attendance pipeline using ArcFace + InsightFace")
    parser.add_argument("image", help="Path to class photo image")
    parser.add_argument("--db", dest="db", default="arcface_embeddings.pkl", help="Embeddings DB path")
    parser.add_argument("--students-dir", dest="students_dir", default=None, help="If DB missing, build from this directory (hierarchical by default)")
    parser.add_argument("--output-dir", dest="output_dir", default="recognition_outputs")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--save-crops", action="store_true")
    parser.add_argument("--wandb", action="store_true", help="Enable Weights & Biases logging")
    parser.add_argument("--wandb-project", default="face-attendance")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack name")
    parser.add_argument("--max-per-id", type=int, default=None, help="When building DB, cap images per identity")
    parser.add_argument("--student-map", default=None, help="Path to student_mapping.json to enrich CSV with roll & name")

    args = parser.parse_args()

    db_path = maybe_build_db_if_missing(
        db_path=args.db,
        students_dir=args.students_dir,
        hierarchical=True,
        max_per_id=args.max_per_id,
        model_name=args.model,
    )

    # Optional student mapping
    student_map = None
    if args.student_map and os.path.exists(args.student_map):
        try:
            with open(args.student_map, "r", encoding="utf-8") as f:
                student_map = json.load(f)
        except Exception as e:
            print(f"[warn] Could not load student map: {e}")

    result = recognize_class_image(
        image_path=args.image,
        db_path=db_path,
        output_root=args.output_dir,
        threshold=args.threshold,
        save_crops=args.save_crops,
        wandb_enable=args.wandb,
        wandb_project=args.wandb_project,
        model_name=args.model,
        student_map=student_map,
    )

    # If we have a mapping, also write a full CSV with roll & name
    if student_map:
        full_rows: List[Dict[str, str]] = []
        for r in result["attendance_rows"]:
            sid = str(r["student_id"]).strip()
            # If identities in DB are like '1' derived from '1.jpg', this matches keys in student_map
            info = student_map.get(sid)
            full_rows.append(
                {
                    "timestamp": r["timestamp"],
                    "image": r["image"],
                    "student_id": sid,
                    "roll": str(info.get("roll")) if info else "",
                    "name": str(info.get("name")) if info else "",
                    "similarity": r["similarity"],
                    "bbox": r["bbox"],
                    "status": r["status"],
                }
            )
        write_attendance_csv_full(os.path.join(args.output_dir, "attendance_report_full.csv"), full_rows)

    print("\nRun summary:")
    print(json.dumps({"metrics": result["metrics"], "annotated": result["annotated"], "run_dir": result["run_dir"]}, indent=2))


if __name__ == "__main__":
    main()
import os
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

import cv2
import numpy as np

from arcface_recognition import ArcFaceRecognizer


def ensure_dir(p: str):
    if p:
        os.makedirs(p, exist_ok=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_attendance_csv(csv_path: str, rows: List[Dict[str, str]]):
    ensure_dir(os.path.dirname(csv_path))
    header = ["timestamp", "image", "student_id", "similarity", "bbox", "status"]
    exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def write_attendance_csv_full(csv_path: str, rows: List[Dict[str, str]]):
    """Extended CSV with roll and name columns."""
    ensure_dir(os.path.dirname(csv_path))
    header = [
        "timestamp",
        "image",
        "student_id",
        "roll",
        "name",
        "similarity",
        "bbox",
        "status",
    ]
    exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def save_json(path: str, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_wandb(
    enabled: bool,
    project: str,
    run_name: str,
    config: dict,
    metrics: dict,
    annotated_img_path: Optional[str],
    predictions: List[dict],
    db_path: Optional[str] = None,
):
    if not enabled:
        return
    try:
        import wandb  # type: ignore
    except Exception as e:
        print(f"[wandb] Not logging (import failed): {e}")
        return

    wandb.init(project=project, name=run_name, config=config)
    wandb.log(metrics)

    # Log annotated image
    if annotated_img_path and os.path.exists(annotated_img_path):
        img = wandb.Image(annotated_img_path, caption=f"Annotated {Path(annotated_img_path).name}")
        wandb.log({"annotated": img})

    # Log predictions table
    if predictions:
        columns = ["identity", "name", "roll", "similarity", "bbox", "status"]
        data = [[
            p.get("identity"),
            p.get("mapped_name"),
            p.get("mapped_roll"),
            float(p.get("similarity", 0.0)),
            str(p.get("bbox")),
            p.get("status"),
        ] for p in predictions]
        table = wandb.Table(columns=columns, data=data)
        wandb.log({"predictions": table})

    # Register the embeddings DB as an artifact for traceability
    if db_path and os.path.exists(db_path):
        art = wandb.Artifact("arcface_embeddings", type="embeddings-db")
        art.add_file(db_path)
        wandb.log_artifact(art)

    wandb.finish()


def recognize_class_image(
    image_path: str,
    db_path: str,
    output_root: str = "recognition_outputs",
    threshold: float = 0.35,
    save_crops: bool = True,
    wandb_enable: bool = False,
    wandb_project: str = "face-attendance",
    model_name: str = "buffalo_l",
    student_map: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Run detection+recognition on a class photo and persist outputs + metrics.

    Returns a dict with summary, metrics, and paths.
    """
    recognizer = ArcFaceRecognizer(model_name=model_name)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Embeddings DB not found: {db_path}. Build it first using arcface_recognition.py build ...")

    db = recognizer.load_db(db_path)

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # Detect+embed using InsightFace (handles alignment)
    faces = recognizer.app.get(img)

    ts = now_stamp()
    run_dir = os.path.join(output_root, ts)
    crops_dir = os.path.join(run_dir, "crops")
    ensure_dir(run_dir)
    if save_crops:
        ensure_dir(crops_dir)

    annotated = img.copy()
    predictions: List[dict] = []
    recognized_count = 0
    similarities: List[float] = []

    for idx, face in enumerate(faces):
        emb = face.normed_embedding.astype(np.float32)
        name, sim = recognizer._best_match(emb, db, threshold)
        x1, y1, x2, y2 = map(int, face.bbox)
        status = "recognized" if name != "UNKNOWN" else "unknown"
        if status == "recognized":
            recognized_count += 1
            similarities.append(sim)

        # Build display label using student_map if available
        mapped_name = None
        mapped_roll = None
        if status == "recognized" and student_map is not None:
            info = student_map.get(str(name))
            if isinstance(info, dict):
                mapped_name = info.get("name")
                mapped_roll = info.get("roll")

        color = (0, 255, 0) if status == "recognized" else (0, 0, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        if status == "recognized" and mapped_name:
            label = f"{mapped_name} ({mapped_roll}) : {sim:.2f}"
        elif status == "recognized":
            label = f"{name}:{sim:.2f}"
        else:
            label = f"UNKNOWN:{sim:.2f}"
        cv2.putText(annotated, label, (x1, max(10, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        if save_crops:
            crop = img[max(0, y1):y2, max(0, x1):x2]
            if crop.size > 0:
                crop_path = os.path.join(crops_dir, f"face_{idx+1}_{name}.jpg")
                cv2.imwrite(crop_path, crop)
        else:
            crop_path = None

        predictions.append(
            {
                "identity": name,
                "similarity": float(sim),
                "bbox": [x1, y1, x2, y2],
                "status": status,
                "crop": crop_path,
                "mapped_name": mapped_name,
                "mapped_roll": mapped_roll,
            }
        )

    annotated_path = os.path.join(run_dir, f"{Path(image_path).stem}_annotated.jpg")
    cv2.imwrite(annotated_path, annotated)

    total_faces = len(faces)
    coverage = (recognized_count / total_faces) if total_faces > 0 else 0.0
    mean_sim = float(np.mean(similarities)) if similarities else 0.0
    median_sim = float(np.median(similarities)) if similarities else 0.0
    unknown_rate = 1.0 - coverage

    # A simple unlabeled selection score: prioritize recognizing more faces with strong confidence
    # You can tune weights per your preference.
    score = coverage * mean_sim

    metrics = {
        "total_faces": total_faces,
        "recognized": recognized_count,
        "coverage": coverage,
        "unknown_rate": unknown_rate,
        "mean_similarity": mean_sim,
        "median_similarity": median_sim,
        "score": score,
        "threshold": threshold,
    }

    # Persist prediction JSON for traceability
    meta = {
        "image": image_path,
        "timestamp": ts,
        "predictions": predictions,
        "metrics": metrics,
    }
    save_json(os.path.join(run_dir, "predictions.json"), meta)

    # Append attendance CSV (only recognized students)
    attendance_rows = []
    for p in predictions:
        if p["identity"] != "UNKNOWN":
            attendance_rows.append(
                {
                    "timestamp": ts,
                    "image": image_path,
                    "student_id": p["identity"],
                    "similarity": f"{p['similarity']:.4f}",
                    "bbox": str(tuple(p["bbox"])),
                    "status": p["status"],
                }
            )
    write_attendance_csv(os.path.join(output_root, "attendance_report.csv"), attendance_rows)

    # Optional: log to W&B
    log_wandb(
        enabled=wandb_enable,
        project=wandb_project,
        run_name=f"attendance_{ts}",
        config={
            "model": model_name,
            "db_path": db_path,
            "threshold": threshold,
        },
        metrics=metrics,
        annotated_img_path=annotated_path,
        predictions=predictions,
        db_path=db_path,
    )

    return {
        "run_dir": run_dir,
        "annotated": annotated_path,
        "metrics": metrics,
        "attendance_rows": attendance_rows,
    }


def maybe_build_db_if_missing(
    db_path: str,
    students_dir: Optional[str],
    hierarchical: bool = True,
    max_per_id: Optional[int] = None,
    model_name: str = "buffalo_l",
) -> str:
    if os.path.exists(db_path):
        return db_path
    if not students_dir:
        raise FileNotFoundError(
            f"Embeddings DB '{db_path}' not found and no students_dir provided to build it."
        )
    print(f"[build-db] Building embeddings DB from {students_dir} -> {db_path}")
    recognizer = ArcFaceRecognizer(model_name=model_name)
    recognizer.build_embeddings_db(
        faces_dir=students_dir,
        db_path=db_path,
        hierarchical=hierarchical,
        max_images_per_identity=max_per_id,
    )
    return db_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Attendance pipeline using ArcFace + InsightFace")
    parser.add_argument("image", help="Path to class photo image")
    parser.add_argument("--db", dest="db", default="arcface_embeddings.pkl", help="Embeddings DB path")
    parser.add_argument("--students-dir", dest="students_dir", default=None, help="If DB missing, build from this directory (hierarchical by default)")
    parser.add_argument("--output-dir", dest="output_dir", default="recognition_outputs")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--save-crops", action="store_true")
    parser.add_argument("--wandb", action="store_true", help="Enable Weights & Biases logging")
    parser.add_argument("--wandb-project", default="face-attendance")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack name")
    parser.add_argument("--max-per-id", type=int, default=None, help="When building DB, cap images per identity")
    parser.add_argument("--student-map", default=None, help="Path to student_mapping.json to enrich CSV with roll & name")

    args = parser.parse_args()

    db_path = maybe_build_db_if_missing(
        db_path=args.db,
        students_dir=args.students_dir,
        hierarchical=True,
        max_per_id=args.max_per_id,
        model_name=args.model,
    )

    # Optional student mapping
    student_map = None
    if args.student_map and os.path.exists(args.student_map):
        try:
            with open(args.student_map, "r", encoding="utf-8") as f:
                student_map = json.load(f)
        except Exception as e:
            print(f"[warn] Could not load student map: {e}")

    result = recognize_class_image(
        image_path=args.image,
        db_path=db_path,
        output_root=args.output_dir,
        threshold=args.threshold,
        save_crops=args.save_crops,
        wandb_enable=args.wandb,
        wandb_project=args.wandb_project,
        model_name=args.model,
        student_map=student_map,
    )

    # If we have a mapping, also write a full CSV with roll & name
    if student_map:
        full_rows: List[Dict[str, str]] = []
        for r in result["attendance_rows"]:
            sid = str(r["student_id"]).strip()
            # If identities in DB are like '1' derived from '1.jpg', this matches keys in student_map
            info = student_map.get(sid)
            full_rows.append(
                {
                    "timestamp": r["timestamp"],
                    "image": r["image"],
                    "student_id": sid,
                    "roll": str(info.get("roll")) if info else "",
                    "name": str(info.get("name")) if info else "",
                    "similarity": r["similarity"],
                    "bbox": r["bbox"],
                    "status": r["status"],
                }
            )
        write_attendance_csv_full(os.path.join(args.output_dir, "attendance_report_full.csv"), full_rows)

    print("\nRun summary:")
    print(json.dumps({"metrics": result["metrics"], "annotated": result["annotated"], "run_dir": result["run_dir"]}, indent=2))


if __name__ == "__main__":
    main()
