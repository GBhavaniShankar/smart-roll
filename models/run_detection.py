#!/usr/bin/env python3
"""
Simple script to run face detection on all images in org_images folder
"""

from face_detection import process_all_images
import os

def main():
    """Main function to run face detection"""
    
    # Get the current directory (YOLO folder)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define input and output paths relative to YOLO folder
    input_dir = os.path.join(current_dir, "..", "data", "org_images")
    output_dir = os.path.join(current_dir, "..", "output")
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"Error: Input directory not found: {input_dir}")
        return
    
    print("Starting face detection process...")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    # Process all images
    process_all_images(input_dir, output_dir)

if __name__ == "__main__":
    main()