#!/usr/bin/env python3
"""
Example script demonstrating single image face detection
"""

from face_detection import FaceDetector, process_single_image_standalone
import cv2
import os

def example_single_image():
    """Example of processing a single image"""
    
    # Example image path (adjust this to your actual image)
    image_path = "../data/org_images/20250130_140338.jpg"
    output_dir = "../output/single_image_test"
    
    print("Method 1: Using FaceDetector class")
    print("-" * 40)
    
    # Method 1: Using the class
    detector = FaceDetector()
    cropped_faces = detector.process_single_image(image_path, output_dir)
    
    print(f"Cropped {len(cropped_faces)} faces and saved to {output_dir}")
    
    print("\nMethod 2: Using standalone function")
    print("-" * 40)
    
    # Method 2: Using standalone function (without saving)
    faces = process_single_image_standalone(image_path)
    
    print(f"Got {len(faces)} face crops in memory")
    
    # You can now work with the cropped faces
    for i, face in enumerate(faces):
        print(f"Face {i+1}: Shape = {face.shape}")
        # Example: You could process each face further here
        # face_resized = cv2.resize(face, (224, 224))  # Resize for ML model
        # face_gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)  # Convert to grayscale

def process_custom_image():
    """Process a custom image path"""
    
    # Get image path from user
    image_path = input("Enter the path to your image: ").strip()
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return
    
    output_dir = input("Enter output directory (or press Enter to skip saving): ").strip()
    
    if not output_dir:
        output_dir = None
    
    # Process the image
    faces = process_single_image_standalone(image_path, output_dir)
    
    if faces:
        print(f"Successfully extracted {len(faces)} faces!")
        if output_dir:
            print(f"Faces saved to: {output_dir}")
    else:
        print("No faces detected in the image.")

if __name__ == "__main__":
    print("Single Image Face Detection Demo")
    print("=" * 40)
    
    choice = input("Choose option:\n1. Run example\n2. Process custom image\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        example_single_image()
    elif choice == "2":
        process_custom_image()
    else:
        print("Invalid choice. Running example...")
        example_single_image()