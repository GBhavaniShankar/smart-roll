#!/usr/bin/env python3
"""
Complete YOLO Face Detection System
Combines face detection, batch processing, and single image processing in one file
"""

import cv2
import os
from ultralytics import YOLO
import numpy as np
from pathlib import Path
import argparse
import sys

class FaceDetector:
    def __init__(self, model_path=None):
        """Initialize YOLO face detector with the best available model"""
        if model_path is None:
            # Use YOLOv8m for face detection (medium model - better accuracy)
            self.model = YOLO('yolov8m.pt')
        else:
            self.model = YOLO(model_path)
    
    def detect_faces(self, image_path, output_dir):
        """
        Detect faces in an image and save results with full structure
        
        Args:
            image_path (str): Path to input image
            output_dir (str): Directory to save outputs
        """
        # Create output directory structure
        image_name = Path(image_path).stem
        image_output_dir = os.path.join(output_dir, image_name)
        cropped_dir = os.path.join(image_output_dir, 'cropped_faces')
        
        os.makedirs(image_output_dir, exist_ok=True)
        os.makedirs(cropped_dir, exist_ok=True)
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image {image_path}")
            return None
        
        # Copy original image to output folder
        original_path = os.path.join(image_output_dir, f'{image_name}_original.jpg')
        cv2.imwrite(original_path, image)
        
        # Run YOLO detection
        results = self.model(image_path, classes=[0])  # class 0 is 'person' in COCO dataset
        
        # Create a copy for drawing detections
        detected_image = image.copy()
        face_count = 0
        
        # Process detections
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    confidence = float(box.conf[0])
                    
                    # Only process high confidence detections
                    if confidence > 0.5:
                        # Draw bounding box on detected image
                        cv2.rectangle(detected_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(detected_image, f'Face: {confidence:.2f}', 
                                  (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        # Crop face from original image
                        face_crop = image[y1:y2, x1:x2]
                        
                        # Save cropped face
                        face_count += 1
                        crop_path = os.path.join(cropped_dir, f'face_{face_count}.jpg')
                        cv2.imwrite(crop_path, face_crop)
        
        # Save detected image with bounding boxes
        detected_path = os.path.join(image_output_dir, f'{image_name}_detected.jpg')
        cv2.imwrite(detected_path, detected_image)
        
        print(f"Processed {image_name}: Found {face_count} faces")
        return face_count
    
    def process_single_image(self, image_path, output_dir=None):
        """
        Process a single image and return cropped faces
        
        Args:
            image_path (str): Path to input image
            output_dir (str, optional): Directory to save outputs. If None, only returns cropped faces
            
        Returns:
            list: List of cropped face images as numpy arrays
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image {image_path}")
            return []
        
        # Run YOLO detection
        results = self.model(image_path, classes=[0])  # class 0 is 'person' in COCO dataset
        
        cropped_faces = []
        face_count = 0
        
        # Process detections
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    confidence = float(box.conf[0])
                    
                    # Only process high confidence detections
                    if confidence > 0.5:
                        # Crop face from original image
                        face_crop = image[y1:y2, x1:x2]
                        cropped_faces.append(face_crop)
                        
                        # Save cropped face if output directory is provided
                        if output_dir is not None:
                            face_count += 1
                            os.makedirs(output_dir, exist_ok=True)
                            image_name = Path(image_path).stem
                            crop_path = os.path.join(output_dir, f'{image_name}_face_{face_count}.jpg')
                            cv2.imwrite(crop_path, face_crop)
        
        print(f"Found {len(cropped_faces)} faces in {Path(image_path).name}")
        return cropped_faces

def process_all_images(input_dir, output_dir):
    """
    Process all images in the input directory
    
    Args:
        input_dir (str): Directory containing input images
        output_dir (str): Directory to save all outputs
    """
    # Initialize face detector
    detector = FaceDetector()
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Supported image extensions
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    # Process each image
    total_faces = 0
    processed_images = 0
    
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        
        # Check if file is an image
        if os.path.isfile(file_path) and Path(filename).suffix.lower() in supported_extensions:
            print(f"Processing: {filename}")
            faces_found = detector.detect_faces(file_path, output_dir)
            
            if faces_found is not None:
                total_faces += faces_found
                processed_images += 1
    
    print(f"\nProcessing complete!")
    print(f"Images processed: {processed_images}")
    print(f"Total faces detected: {total_faces}")

def process_single_image_standalone(image_path, output_dir=None, model_path=None):
    """
    Standalone function to process a single image
    
    Args:
        image_path (str): Path to input image
        output_dir (str, optional): Directory to save cropped faces
        model_path (str, optional): Path to custom YOLO model
        
    Returns:
        list: List of cropped face images as numpy arrays
    """
    detector = FaceDetector(model_path)
    return detector.process_single_image(image_path, output_dir)

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

def interactive_demo():
    """Interactive demo for single image processing"""
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

def run_batch_detection():
    """Run batch detection on all images"""
    
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define input and output paths relative to current folder
    input_dir = os.path.join(current_dir, "..", "data", "org_images")
    output_dir = os.path.join(current_dir, "..", "output")
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"Error: Input directory not found: {input_dir}")
        return
    
    print("Starting batch face detection process...")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    # Process all images
    process_all_images(input_dir, output_dir)

def main():
    """Main function with command line interface"""
    
    parser = argparse.ArgumentParser(description='YOLO Face Detection System')
    parser.add_argument('--mode', choices=['batch', 'single', 'demo'], default='batch',
                       help='Processing mode: batch (all images), single (one image), demo (interactive)')
    parser.add_argument('--input', type=str, help='Input image path (for single mode)')
    parser.add_argument('--output', type=str, help='Output directory')
    parser.add_argument('--input-dir', type=str, help='Input directory (for batch mode)')
    
    args = parser.parse_args()
    
    if args.mode == 'batch':
        if args.input_dir and args.output:
            process_all_images(args.input_dir, args.output)
        else:
            run_batch_detection()
    
    elif args.mode == 'single':
        if not args.input:
            print("Error: --input required for single mode")
            return
        
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            return
        
        faces = process_single_image_standalone(args.input, args.output)
        print(f"Extracted {len(faces)} faces from {args.input}")
        
        if args.output:
            print(f"Faces saved to: {args.output}")
    
    elif args.mode == 'demo':
        interactive_demo()

if __name__ == "__main__":
    # If no command line arguments, show menu
    if len(sys.argv) == 1:
        print("YOLO Face Detection System")
        print("=" * 30)
        print("1. Batch process all images")
        print("2. Process single image")
        print("3. Interactive demo")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            run_batch_detection()
        elif choice == "2":
            image_path = input("Enter image path: ").strip()
            output_dir = input("Enter output directory (optional): ").strip() or None
            
            if os.path.exists(image_path):
                faces = process_single_image_standalone(image_path, output_dir)
                print(f"Extracted {len(faces)} faces")
            else:
                print("Image not found!")
        elif choice == "3":
            interactive_demo()
        elif choice == "4":
            print("Goodbye!")
        else:
            print("Invalid choice. Running batch processing...")
            run_batch_detection()
    else:
        main()


  