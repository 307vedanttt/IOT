"""
register_student.py — Student Enrollment Script
=================================================
"""

import cv2
import os
import sys
import time
import numpy as np
import qrcode
from PIL import Image
from face_utils import encode_face, save_encoding
from local_db import init_db, register_student, get_student

FACES_DIR = "../data/faces"
os.makedirs(FACES_DIR, exist_ok=True)

def get_student_details() -> dict:
    """Prompt for student_id, name, department via input()."""
    print("\n--- Register New Student ---")
    while True:
        student_id = input("Student ID (e.g., STU2024001): ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            continue
        existing = get_student(student_id)
        if existing:
            print(f"Warning: Student {student_id} already exists ({existing['name']}).")
            confirm = input("Overwrite? (y/n): ").strip().lower()
            if confirm != 'y':
                continue
        break
    
    name = input("Student Name: ").strip()
    department = input("Department: ").strip()
    return {'student_id': student_id, 'name': name, 'department': department}

def capture_faces_from_webcam(num_images=5):
    """
    Capture multiple face images to average for a robust embedding.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return []

    encodings = []
    print(f"\nWe need to capture {num_images} face angles.")
    print("Please look slightly different ways (straight, left, right, up, down).")
    
    count = 0
    while count < num_images:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        # Show instructions
        display_frame = frame.copy()
        cv2.putText(display_frame, f"Captured: {count}/{num_images}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(display_frame, "Press SPACE to capture", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow("Face Enrollment", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            print(f"Capturing image {count+1}...")
            encoding = encode_face(frame)
            if encoding is not None:
                encodings.append(encoding)
                count += 1
                print("Face detected and encoded.")
                # Save the first frame for reference
                if count == 1:
                    global first_frame
                    first_frame = frame.copy()
            else:
                print("No face detected in that frame! Try again.")
                
            time.sleep(1) # brief pause to let them change pose
            
        elif key == ord('q'):
            print("Capture cancelled.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return encodings

def generate_qr_code(student_id: str) -> None:
    """Generate a QR code image encoding the student_id."""
    payload = f"student_id:{student_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    path = os.path.join(FACES_DIR, f"{student_id}_qr.png")
    img.save(path)
    print(f"QR code saved to: {path}")

def main():
    init_db()
    details = get_student_details()
    
    global first_frame
    first_frame = None
    
    encodings = capture_faces_from_webcam(num_images=5)
    if not encodings:
        print("Enrollment failed. No faces captured.")
        sys.exit(1)
        
    print("\nAveraging face encodings for robust match...")
    avg_encoding = np.mean(encodings, axis=0)
    
    save_encoding(details['student_id'], avg_encoding)
    
    if first_frame is not None:
        cv2.imwrite(os.path.join(FACES_DIR, f"{details['student_id']}.jpg"), first_frame)
        
    register_student(details['student_id'], details['name'], details['department'])
    generate_qr_code(details['student_id'])
    
    print("\n✅ Student registered successfully!")

if __name__ == "__main__":
    main()
