# test_model.py
import insightface
import cv2
import numpy as np
import os
import traceback

# --- Config ---
# Make sure your image file is in the same folder as this script
IMAGE_PATH = "../student_pics/rahul.jpeg"  
# --------------

print("--- Test Script Started ---")
print(f"Current working directory: {os.getcwd()}")

try:
    # 1. Check if image file exists
    if not os.path.exists(IMAGE_PATH):
        print(f"FATAL ERROR: Image file not found at: {IMAGE_PATH}")
        exit()

    # 2. Load the model (same as in your app)
    print("Loading ArcFace model (buffalo_l)...")
    model = insightface.app.FaceAnalysis(
        name="buffalo_l", 
        providers=['CPUExecutionProvider']
    )
    model.prepare(ctx_id=0, det_size=(640, 640))
    print("Model loaded successfully.")

    # 3. Load the image from disk using cv2
    print(f"Loading image from: {IMAGE_PATH}")
    image = cv2.imread(IMAGE_PATH)
    
    if image is None:
        print(f"FATAL ERROR: cv2.imread() failed. The image file might be corrupt.")
        exit()
    
    print(f"Image loaded successfully (dimensions: {image.shape}).")

    # 4. Get the face embedding
    print("Attempting to find face and get embedding...")
    faces = model.get(image)
    
    # 5. Print results
    if not faces:
        print("\n--- 🔴 TEST FAILED ---")
        print("ERROR: No face was detected in the image.")
        print("This is why your app is crashing.")
    
    elif len(faces) > 1:
        print("\n--- 🟡 TEST WARNING ---")
        print(f"Warning: {len(faces)} faces detected. Using the first one.")
        embedding = faces[0].normed_embedding
        print(f"Embedding (first 5 values): {embedding[:5]}")
        print("Model is working, but the image may not be ideal for registration.")
    
    else:
        embedding = faces[0].normed_embedding
        print("\n--- 🟢 TEST SUCCESSFUL! ---")
        print("One face found and embedding extracted.")
        print(f"Embedding (first 5 values): {embedding[:5]}")
        print(f"Embedding dimensions: {embedding.shape}")

except Exception as e:
    print("\n--- 🔴 TEST CRASHED ---")
    print(f"An unexpected error occurred: {e}")
    traceback.print_exc()

print("--- Test Script Finished ---")