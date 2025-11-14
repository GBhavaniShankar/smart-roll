import wandb
import os
import cv2
import json
import numpy as np
from typing import Dict, List, Any
from pathlib import Path

try:
    from arcface_recognizer import ArcFaceRecognizer, _log
except ImportError:
    print("Error: Make sure 'arcface_recognizer.py' is in the same directory.")
    exit()

_log("Starting Initial Offline Evaluation...")
MODEL_NAME = "buffalo_l"
GRID_SEARCH = {
    "det_size": [(320, 320), (640, 640)],
    "det_thresh": [0.3, 0.5],
    "rec_thresh": [0.1, 0.2, 0.3]
}
VALIDATION_DIR = Path("validation_data")
IMAGE_DIR = VALIDATION_DIR / "images"
ENROLLMENT_FILE = VALIDATION_DIR / "enrollment.json"

_log(f"Loading enrollment data from {ENROLLMENT_FILE}")
with open(ENROLLMENT_FILE, 'r') as f:
    enrolled_data = json.load(f)

enrolled_db: Dict[str, np.ndarray] = {}
for student in enrolled_data.get("enrolled_students", []):
    sid = student.get("student_id")
    embedding = student.get("face_embedding") 
    if not sid or not embedding: continue
    enrolled_db[sid] = np.asarray(embedding, dtype=np.float32)

_log(f"Loaded {len(enrolled_db)} total students for evaluation.")
image_files = list(IMAGE_DIR.glob("*.jpg")) + list(IMAGE_DIR.glob("*.png")) + list(IMAGE_DIR.glob("*.jpeg"))
_log(f"Found {len(image_files)} images to test.")
if not image_files:
    _log("FATAL: No images found in validation_data/images/. Please add class photos.")
    exit()

# 4. INITIALIZE W&B & RUN SEARCH
_log("Initializing W&B Run...")
run = wandb.init(
    project="attendance-evaluation",
    job_type="initial-hyperparam-search",
    config={"model_name": MODEL_NAME}
)

summary_table = wandb.Table(columns=["avg_coverage", "det_size", "det_thresh", "rec_thresh"])
best_combo = None
all_combo_results = [] 
best_coverage = -1.0 # Initialize best_coverage

for det_size in GRID_SEARCH["det_size"]:
    for det_thresh in GRID_SEARCH["det_thresh"]:
        _log(f"Loading model: {MODEL_NAME} (size={det_size}, thresh={det_thresh})")
        recognizer = ArcFaceRecognizer(
            model_name=MODEL_NAME, det_size=det_size, det_thresh=det_thresh
        )
        for rec_thresh in GRID_SEARCH["rec_thresh"]:
            combo_name = f"size:{det_size}_det:{det_thresh}_rec:{rec_thresh}"
            total_coverage = 0.0
            num_images_processed = 0
            
            for img_path in image_files:
                img_bgr = cv2.imread(str(img_path))
                if img_bgr is None: continue
                result = recognizer.recognize_from_enrolled(
                    img_bgr, enrolled_db, threshold=rec_thresh
                )
                total_coverage += result["metrics"]["coverage"]
                num_images_processed += 1
            
            avg_coverage = (total_coverage / num_images_processed) if num_images_processed > 0 else 0
            _log(f"  [{combo_name}] -> Avg. Coverage: {avg_coverage:.2f}")
            
            combo_data = {
                "avg_coverage": avg_coverage,
                "model_name": MODEL_NAME,
                "det_size": det_size, 
                "det_thresh": det_thresh,
                "rec_thresh": rec_thresh,
                "last_evaluation_week": 0  # KEY: This is the "Week 0" static data
            }
            all_combo_results.append(combo_data) 
            
            # Tie-breaker logic
            is_better = False
            if best_combo is None:
                is_better = True
            elif combo_data["avg_coverage"] > best_combo["avg_coverage"]:
                is_better = True
            elif combo_data["avg_coverage"] == best_combo["avg_coverage"]:
                if combo_data["det_size"][0] < best_combo["det_size"][0]:
                    is_better = True
                elif combo_data["det_size"][0] == best_combo["det_size"][0]:
                    if combo_data["det_thresh"] > best_combo["det_thresh"]:
                        is_better = True
                    elif combo_data["det_thresh"] == best_combo["det_thresh"]:
                        if combo_data["rec_thresh"] > best_combo["rec_thresh"]:
                            is_better = True
            if is_better:
                best_coverage = avg_coverage
                best_combo = combo_data


# LOG CUSTOM BAR CHART & ARTIFACT
_log("Generating custom bar chart...")
plot_table = wandb.Table(columns=["configuration_label", "avg_coverage"])
for r in all_combo_results:
    label = f"Size:{r['det_size']}\nDet:{r['det_thresh']}\nRec:{r['rec_thresh']}"
    plot_table.add_data(label, r["avg_coverage"])

wandb.log({
    "coverage_comparison_chart": wandb.plot.bar(
        plot_table, "configuration_label", "avg_coverage", 
        title="Initial Hyperparameter Performance"
    )
})

# Save champion artifact
if best_combo:
    _log(f"The winning combination is: {best_combo}")
    champion_file = "champion.json"
    with open(champion_file, 'w') as f:
        json.dump(best_combo, f, indent=2) 
    
    artifact = wandb.Artifact(name="champion_settings", type="config")
    artifact.add_file(champion_file)
    run.log_artifact(artifact)
    _log("Initial champion artifact uploaded to W&B.")

run.log({"evaluation_summary_table": summary_table})
run.finish()