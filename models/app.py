import uvicorn
import wandb
import os
import numpy as np
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple

# --- Import from our recognizer.py file ---
try:
    from arcface_recognizer import ArcFaceRecognizer, _log, _decode_base64_image_to_bgr
except ImportError:
    print("Error: Make sure 'arcface_recognizer.py' is in the same directory.")
    exit()

CHAMPION_SETTINGS: Dict[str, Any] = {}
recognizer_champion: ArcFaceRecognizer

class StudentEmbedding(BaseModel):
    student_id: str
    face_embedding: List[float]

class AttendanceRequest(BaseModel):
    class_image: str
    course_id: str
    enrolled_students: List[StudentEmbedding] 

class RecognitionMetrics(BaseModel):
    total_faces_detected: int
    recognized_faces_count: int
    coverage: float
    threshold_used: float
    model_used: str

class AttendanceResponse(BaseModel):
    present_students: List[str]
    confidence_scores: Dict[str, float]
    metrics: RecognitionMetrics
    unknown_faces: List[str] = Field(default=[], description="List of base64-encoded unknown faces for review.")

app = FastAPI(
    title="Dynamic Champion Attendance API",
    description="Loads champion settings from W&B Artifacts and flags unknowns.",
    version="6.0.0"
)

@app.on_event("startup")
def load_champion_from_wandb():
    """
    On server startup, log into W&B, download the latest
    champion_settings artifact, and load the model.
    """
    global recognizer_champion, CHAMPION_SETTINGS
    WANDB_API_KEY = os.environ.get("WANDB_API_KEY")
    
    if not WANDB_API_KEY:
        _log("FATAL: WANDB_API_KEY secret not found!")
        raise RuntimeError("WANDB_API_KEY not set.")
        
    _log("Logging into W&B to download champion artifact...")
    
    try:
        wandb.login(key=WANDB_API_KEY)
        run = wandb.init(
            project="attendance-evaluation", # Project where artifact is saved
            job_type="server_startup"
        )
        artifact = run.use_artifact('champion_settings:latest')
        artifact_dir = artifact.download()
        
        champion_file_path = os.path.join(artifact_dir, "champion.json")
        with open(champion_file_path, 'r') as f:
            CHAMPION_SETTINGS = json.load(f)
            
        _log(f"Successfully loaded champion settings: {CHAMPION_SETTINGS}")
        run.finish()

    except Exception as e:
        _log(f"FATAL: Could not load champion artifact from W&B. Error: {e}")
        if 'run' in locals() and run.id:
            run.finish()
        raise e
        
    _log(f"Server starting, loading CHAMPION model...")
    try:
        det_size_tuple = tuple(CHAMPION_SETTINGS["det_size"])
        
        recognizer_champion = ArcFaceRecognizer(
            model_name=CHAMPION_SETTINGS["model_name"],
            det_size=det_size_tuple,
            det_thresh=CHAMPION_SETTINGS["det_thresh"]
        )
        _log("Champion model loaded successfully.")
    except Exception as e:
        _log(f"FATAL: Could not load champion model. Error: {e}")
        raise e

@app.post("/recognize", response_model=AttendanceResponse)
def take_attendance(request: AttendanceRequest) -> Dict:
    """
    Runs the champion model, logs to W&B, and
    fires a programmatic alert if drift is detected.
    """
    
    # W&B Setup 
    WANDB_API_KEY = os.environ.get("WANDB_API_KEY")
    run: Optional[wandb.sdk.wandb_run.Run] = None
    if WANDB_API_KEY:
        try:
            wandb.login(key=WANDB_API_KEY)
            run = wandb.init(
                project="attendance-monitoring", 
                job_type="live_inference",
                config=CHAMPION_SETTINGS 
            )
        except Exception as e:
            _log(f"W&B init (monitoring) failed: {e}")

    try:
        img_bgr = _decode_base64_image_to_bgr(request.class_image)
        enrolled_db: Dict[str, np.ndarray] = {}
        for student in request.enrolled_students:
            enrolled_db[student.student_id] = np.asarray(student.face_embedding, dtype=np.float32)
    except ValueError as e:
        if run: run.finish()
        raise HTTPException(status_code=400, detail=f"Image decode error: {e}")

    rec_thresh = CHAMPION_SETTINGS["rec_thresh"]
    model_name = CHAMPION_SETTINGS["model_name"]
    baseline_coverage = CHAMPION_SETTINGS["avg_coverage"]
    
    result = recognizer_champion.recognize_from_enrolled(
        img_bgr,
        enrolled_db,
        threshold=rec_thresh 
    )
    result["metrics"]["model_used"] = model_name

    # Log to W&B and Fire Alert if model drift detected
    if run:
        try:
            live_coverage = result["metrics"]["coverage"]
            drift_percent = 0.0
            if baseline_coverage > 0:
                drift = (baseline_coverage - live_coverage) / baseline_coverage
                drift_percent = drift * 100.0

            run.log({
                "live_coverage": live_coverage,
                "coverage_drift_percent": drift_percent, 
                "total_faces_detected": result["metrics"]["total_faces_detected"],
                "unknown_faces_found": len(result.get("unknown_faces", []))
            })
            
            if drift_percent > 10.0: # 10% drift trigger
                _log(f"WARNING: Model drift detected! ({drift_percent:.1f}% drop)")
                run.alert(
                    title="Model Drift Detected!",
                    text=f"Live coverage ({live_coverage:.2f}) has dropped more than 10% below baseline ({baseline_coverage:.2f}). Re-evaluation may be needed.",
                    level=wandb.AlertLevel.WARN
                )

            run.finish()
        except Exception as e:
            _log(f"W&B log/alert failed: {e}")

    # 4. Return the result
    return result

@app.get("/")
def read_root():
    return {"status": f"ArcFace Champion Server running with: {CHAMPION_SETTINGS}"}