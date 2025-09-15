import cv2
import os
from ultralytics import YOLO
import numpy as np
from pathlib import Path

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
        Detect faces in an image and save results
        
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
            return
        
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

if __name__ == "__main__":
    # Define paths
    input_directory = "../data/org_images"
    output_directory = "../output_medium"
    
    # Process all images
    process_all_images(input_directory, output_directory)