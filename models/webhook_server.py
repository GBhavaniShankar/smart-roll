import uvicorn
import wandb
import os
import cv2
import json
import numpy as np
from typing import Dict, List, Any
from pathlib import Path
import threading
from fastapi import FastAPI, Request
from supabase import create_client, Client

# --- Import from our recognizer.py file ---
try:
    from arcface_recognizer import ArcFaceRecognizer, _log
except ImportError:
    print("Error: Make sure 'arcface_recognizer.py' is in the same directory.")
    exit()

# ------------------------------------------------------------------
# 1. SCRIPT SETTINGS
# ------------------------------------------------------------------
_log("Automation server is starting...")
MODEL_NAME = "buffalo_l"
GRID_SEARCH = {
    "det_size": [(320, 320), (640, 640)],
    "det_thresh": [0.3, 0.5],
    "rec_thresh": [0.1, 0.2, 0.3]
}
# Supabase settings from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = "evaluation_photos"
WANDB_API_KEY = os.environ.get("WANDB_API_KEY") # Needed for the worker thread

# ------------------------------------------------------------------
# 2. THE RE-EVALUATION FUNCTION (This is your "finetune" logic)
# ------------------------------------------------------------------
def run_automated_evaluation():
    _log("[Job] --- Automated Re-evaluation Job Started ---")
    
    # --- 1. Connect to W&B and get OLD champion ---
    _log("[Job] Logging into W&B to get old champion...")
    if not WANDB_API_KEY:
        _log("[Job] ERROR: WANDB_API_KEY not set. Aborting worker.")
        return
        
    wandb.login(key=WANDB_API_KEY)
    run = wandb.init(project="attendance-evaluation", job_type="re-evaluation")
    artifact = run.use_artifact('champion_settings:latest')
    artifact_dir = artifact.download()
    
    with open(os.path.join(artifact_dir, "champion.json"), 'r') as f:
        old_champion = json.load(f)
    
    # This is your "Week 5" (the last time you trained)
    last_eval_week = old_champion.get("last_evaluation_week", 0) 
    _log(f"[Job] Old champion was from Week {last_eval_week}.")

    # --- 2. Connect to Supabase and get NEW data ---
    _log(f"[Job] Connecting to Supabase to find new data...")
    if not SUPABASE_URL or not SUPABASE_KEY:
        _log("[Job] ERROR: Supabase credentials not set. Aborting.")
        run.finish()
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Find the newest week of data in the database (e.g., "Week 8")
    data = supabase.table("evaluation_photos").select("evaluation_week").order("evaluation_week", desc=True).limit(1).execute()
    if not data.data:
        _log("[Job] ERROR: No evaluation photos found in database. Aborting.")
        run.finish()
        return
        
    current_week = data.data[0]['evaluation_week']
    _log(f"[Job] Found new data up to Week {current_week}.")
    
    # This is your "Week 6 to Week 8" logic
    data_range_paths = supabase.table("evaluation_photos").select("storage_path").gt("evaluation_week", last_eval_week).lte("evaluation_week", current_week).execute()
    
    if not data_range_paths.data:
        _log("[Job] No new photos found in the data range. Aborting.")
        run.finish()
        return

    # --- 3. Download New Photos ---
    _log(f"[Job] Downloading {len(data_range_paths.data)} new photos...")
    temp_image_dir = Path("./temp_eval_images")
    temp_image_dir.mkdir(exist_ok=True)
    new_image_files = []

    for item in data_range_paths.data:
        storage_path = item['storage_path']
        local_path = temp_image_dir / Path(storage_path).name
        try:
            with open(local_path, 'wb') as f:
                res = supabase.storage.from_(SUPABASE_BUCKET).download(storage_path)
                f.write(res)
            new_image_files.append(local_path)
        except Exception as e:
            _log(f"[Job] WARN: Failed to download {storage_path}: {e}")

    # --- 4. Load Enrollment DB (for all students) ---
    _log(f"[Job] Loading enrollment database...")
    # This should also be pulled from Supabase, but using file for consistency
    with open("validation_data/enrollment.json", 'r') as f:
        enrolled_data = json.load(f)
    enrolled_db: Dict[str, np.ndarray] = {}
    for student in enrolled_data.get("enrolled_students", []):
        sid = student.get("student_id")
        embedding = student.get("face_embedding") 
        if not sid or not embedding: continue
        enrolled_db[sid] = np.asarray(embedding, dtype=np.float32)

    # --- 5. Run the Hyperparameter Search on NEW Data ---
    _log(f"[Job] Starting hyperparameter search on {len(new_image_files)} images...")
    all_combo_results = []
    new_best_combo = None
    new_best_coverage = -1.0
    
    # Test the Old Champion's performance on the new data
    _log(f"[Job] Testing Old Champion's performance...")
    old_champion_recognizer = ArcFaceRecognizer(
        model_name=old_champion["model_name"],
        det_size=tuple(old_champion["det_size"]),
        det_thresh=old_champion["det_thresh"]
    )
    total_coverage = 0.0
    num_images_processed = 0
    for img_path in new_image_files:
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None: continue
        result = old_champion_recognizer.recognize_from_enrolled(
            img_bgr, enrolled_db, threshold=old_champion["rec_thresh"]
        )
        total_coverage += result["metrics"]["coverage"]
        num_images_processed += 1
    
    old_champion_new_coverage = (total_coverage / num_images_processed) if num_images_processed > 0 else 0
    _log(f"[Job] Old Champion score on new data: {old_champion_new_coverage:.2f}")

    # Run the full grid search to find a new champion
    for det_size in GRID_SEARCH["det_size"]:
        for det_thresh in GRID_SEARCH["det_thresh"]:
            recognizer = ArcFaceRecognizer(
                model_name=MODEL_NAME, det_size=det_size, det_thresh=det_thresh
            )
            for rec_thresh in GRID_SEARCH["rec_thresh"]:
                total_coverage = 0.0
                num_images_processed = 0
                for img_path in new_image_files:
                    img_bgr = cv2.imread(str(img_path))
                    if img_bgr is None: continue
                    result = recognizer.recognize_from_enrolled(
                        img_bgr, enrolled_db, threshold=rec_thresh
                    )
                    total_coverage += result["metrics"]["coverage"]
                    num_images_processed += 1
                
                avg_coverage = (total_coverage / num_images_processed) if num_images_processed > 0 else 0
                
                combo_data = {
                    "avg_coverage": avg_coverage,
                    "model_name": MODEL_NAME,
                    "det_size": det_size, 
                    "det_thresh": det_thresh,
                    "rec_thresh": rec_thresh,
                    "last_evaluation_week": current_week # <-- Set the NEW week
                }
                
                # --- Tie-breaker logic ---
                is_better = False
                if new_best_combo is None: is_better = True
                elif combo_data["avg_coverage"] > new_best_coverage: is_better = True
                elif combo_data["avg_coverage"] == new_best_coverage:
                    if combo_data["det_size"][0] < new_best_combo["det_size"][0]: is_better = True
                    elif combo_data["det_size"][0] == new_best_combo["det_size"][0]:
                        if combo_data["det_thresh"] > new_best_combo["det_thresh"]: is_better = True
                        elif combo_data["det_thresh"] == new_best_combo["det_thresh"]:
                            if combo_data["rec_thresh"] > new_best_combo["rec_thresh"]: is_better = True
                if is_better:
                    new_best_coverage = avg_coverage
                    new_best_combo = combo_data

    # --- 6. Log the Old vs. New Bar Plot ---
    _log(f"[Job] New Champion found with coverage: {new_best_coverage:.2f}")
    
    old_label = f"OldChampion\nSize:{old_champion['det_size']}\nDet:{old_champion['det_thresh']}\nRec:{old_champion['rec_thresh']}"
    new_label = f"NewChampion\nSize:{new_best_combo['det_size']}\nDet:{new_best_combo['det_thresh']}\nRec:{new_best_combo['rec_thresh']}"

    plot_table = wandb.Table(columns=["champion_version", "coverage_on_new_data"])
    plot_table.add_data(old_label, old_champion_new_coverage)
    plot_table.add_data(new_label, new_best_combo["avg_coverage"])
    
    wandb.log({
        "champion_comparison_chart": wandb.plot.bar(
            plot_table, "champion_version", "coverage_on_new_data", 
            title=f"Re-evaluation: Week {last_eval_week+1} to {current_week}"
        )
    })

    # --- 7. Upload the NEW Champion Artifact ---
    _log("[Job] Uploading new champion artifact...")
    champion_file = "champion.json"
    with open(champion_file, 'w') as f:
        json.dump(new_best_combo, f, indent=2)
    
    artifact = wandb.Artifact(name="champion_settings", type="config")
    artifact.add_file(champion_file)
    run.log_artifact(artifact) # This saves it as ":latest"
    
    run.finish()
    _log("[Job] --- Automated Re-evaluation Job Finished ---")

# ------------------------------------------------------------------
# 3. FASTAPI WEBHOOK SERVER
# ------------------------------------------------------------------
app = FastAPI(title="MLOps Automation Worker")

@app.post("/webhook/retrain")
async def trigger_retrain(request: Request):
    """
    This is the endpoint you give to W&B Alerts.
    When performance drops, W&B will call this URL.
    """
    payload = await request.json()
    _log(f"--- [Server] Received W&B Alert! ---")
    _log(f"Alert Title: {payload.get('title')}")
    
    # Start the evaluation job in a separate thread
    threading.Thread(target=run_automated_evaluation).start()
    
    return {"status": "ok", "message": "Re-evaluation job triggered."}

@app.get("/")
def read_root():
    return {"status": "Automation worker is idle and listening for alerts."}

if __name__ == "__main__":
    # This would run on a different port, e.g. 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)