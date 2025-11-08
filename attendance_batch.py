import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional

from attendance_pipeline import (
    recognize_class_image,
    maybe_build_db_if_missing,
)


def ensure_dir(p: str):
    if p:
        os.makedirs(p, exist_ok=True)


def find_images(images_dir: str, exts=("*.jpg", "*.jpeg", "*.png", "*.bmp")) -> List[Path]:
    d = Path(images_dir)
    files: List[Path] = []
    for pat in exts:
        files.extend(sorted(d.glob(pat)))
    return files


def write_summary_csv(path: str, rows: List[Dict[str, str]]):
    ensure_dir(os.path.dirname(path))
    header = [
        "image",
        "total_faces",
        "recognized",
        "coverage",
        "unknown_rate",
        "mean_similarity",
        "median_similarity",
        "score",
        "threshold",
        "run_dir",
        "annotated",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Batch attendance over all images in a folder")
    parser.add_argument("--images-dir", default="org_images", help="Directory with class photos")
    parser.add_argument("--db", default="arcface_embeddings.pkl")
    parser.add_argument("--students-dir", default=None, help="If DB missing, build from this folder")
    parser.add_argument("--student-map", default=None, help="Path to student_mapping.json")
    parser.add_argument("--output-dir", default="recognition_outputs")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--save-crops", action="store_true")
    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--wandb-project", default="face-attendance")
    parser.add_argument("--model", default="buffalo_l")

    args = parser.parse_args()

    # Ensure DB exists (build if needed)
    db_path = maybe_build_db_if_missing(
        db_path=args.db,
        students_dir=args.students_dir,
        hierarchical=(args.students_dir is not None and not any(Path(args.students_dir).glob("*.jpg"))),
        max_per_id=None,
        model_name=args.model,
    )

    # Optional mapping
    student_map: Optional[Dict] = None
    if args.student_map and os.path.exists(args.student_map):
        try:
            with open(args.student_map, "r", encoding="utf-8") as f:
                student_map = json.load(f)
        except Exception as e:
            print(f"[warn] Could not load student map: {e}")

    images = find_images(args.images_dir)
    if not images:
        print(f"No images found under {args.images_dir}")
        return

    print(f"Found {len(images)} class images under {args.images_dir}")

    summary_rows: List[Dict[str, str]] = []

    for img_path in images:
        print(f"\n[run] {img_path}")
        result = recognize_class_image(
            image_path=str(img_path),
            db_path=db_path,
            output_root=args.output_dir,
            threshold=args.threshold,
            save_crops=args.save_crops,
            wandb_enable=args.wandb,
            wandb_project=args.wandb_project,
            model_name=args.model,
            student_map=student_map,
        )
        m = result["metrics"]
        summary_rows.append(
            {
                "image": str(img_path),
                "total_faces": str(m["total_faces"]),
                "recognized": str(m["recognized"]),
                "coverage": f"{m['coverage']:.6f}",
                "unknown_rate": f"{m['unknown_rate']:.6f}",
                "mean_similarity": f"{m['mean_similarity']:.6f}",
                "median_similarity": f"{m['median_similarity']:.6f}",
                "score": f"{m['score']:.6f}",
                "threshold": f"{m['threshold']:.4f}",
                "run_dir": result["run_dir"],
                "annotated": result["annotated"],
            }
        )

    summary_path = os.path.join(args.output_dir, "attendance_summary.csv")
    write_summary_csv(summary_path, summary_rows)

    print("\nBatch complete. Summary written to:")
    print(summary_path)


if __name__ == "__main__":
    main()
