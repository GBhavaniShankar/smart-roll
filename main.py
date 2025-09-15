from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import numpy as np
import cv2

from models.haar_detector import HaarDetector

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For LAN testing; restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# Initialize HaarDetector
detector = HaarDetector()

@app.post("/detect-faces")
async def detect_faces(file: UploadFile = File(...)):
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    faces, annotated = detector.detect_faces(img, return_annotated=True)

    extracted_faces_b64 = [detector.to_base64(face) for face in faces]
    annotated_b64 = detector.to_base64(annotated) if annotated is not None else None

    return JSONResponse(content={
        "faces": extracted_faces_b64,
        "count": len(extracted_faces_b64),
        "annotated": annotated_b64
    })
