# backend/app/utils/face_embedding.py

import asyncio
from typing import List
import numpy as np
import cv2
import insightface
import tempfile  # <-- New import
import os        # <-- New import

# 1. Load the model ONCE when the server starts
try:
    print("Loading ArcFace model (buffalo_l)...")
    arcface_model = insightface.app.FaceAnalysis(
        name="buffalo_l", 
        providers=['CPUExecutionProvider'] 
    )
    arcface_model.prepare(ctx_id=0, det_size=(640, 640))
    print("ArcFace model loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load ArcFace model: {e}")
    arcface_model = None

async def extract_face_embedding(image_bytes: bytes) -> List[float]:
    """
    REAL FUNCTION - Robust Version
    Extracts a face embedding by saving bytes to a temporary file.
    """
    if arcface_model is None:
        raise RuntimeError("ArcFace model is not initialized or failed to load.")
    
    # 1. Create a temporary file to save the uploaded image
    # 'delete=False' is important so we can read it before deleting
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        # 2. Load the image from the temporary file (like the test script)
        image = cv2.imread(temp_file_path)
        
        if image is None:
            raise ValueError("cv2.imread() failed. Uploaded image may be corrupt.")
    
        # 3. Get face information
        faces = arcface_model.get(image)
        
        if not faces:
            raise ValueError("No face detected in the uploaded image.")
            
        if len(faces) > 1:
            print(f"Warning: {len(faces)} faces detected. Using the first one (largest).")
        
        # 4. Get the embedding
        embedding = faces[0].normed_embedding
        
        # 5. Convert to Python list
        return embedding.tolist()

    except Exception as e:
        print(f"Error during face embedding: {e}")
        # Re-raise to be caught by the router
        raise ValueError(f"Failed to process image: {e}")
    
    finally:
        # 6. Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)