"""
main.py — Smart Lab Attendance System
======================================
"""

import cv2
import time
import datetime
from face_utils import detect_faces, encode_face
from qr_utils import detect_qr, draw_qr_box
from matcher import verify
from local_db import init_db, insert_attendance_event, insert_mismatch_log
import firebase_sync

def draw_overlay(frame, text, color, box_points=None, face_box=None):
    """Draw status text and optional bounding boxes."""
    if box_points is not None:
        draw_qr_box(frame, box_points)
    
    if face_box is not None:
        top, right, bottom, left = face_box
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        
    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
    cv2.rectangle(frame, (10, 10), (10 + text_width + 20, 10 + text_height + 20), (0, 0, 0), cv2.FILLED)
    cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

def main():
    print("Initializing Database...")
    init_db()
    
    print("Starting background Firebase sync thread...")
    firebase_sync.start_sync_thread()
    
    print("Starting webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    overlay_text = "System Ready"
    overlay_color = (255, 255, 255) # White
    overlay_time = time.time()
    overlay_duration = 3.0 # seconds

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            break

        qr_result = detect_qr(frame)
        student_id = qr_result['student_id'] if qr_result else None
        qr_points = qr_result['points'] if qr_result else None
        
        face_locations = detect_faces(frame)
        face_encoding = None
        face_box = None
        if face_locations:
            face_box = face_locations[0]
            face_encoding = encode_face(frame, face_locations)

        status, sid = verify(student_id, face_encoding)
        
        now_str = datetime.datetime.now().strftime("%H:%M:%S")

        if status == "MATCH":
            event = insert_attendance_event(sid)
            print(f"[{event['event_type'].upper()}] student_id={sid} at {now_str}")
            overlay_text = f"MATCH: {event['event_type'].upper()}"
            overlay_color = (0, 255, 0)
            overlay_time = time.time()
            
        elif status == "MISMATCH":
            print(f"[PROXY ATTEMPT] card={sid} reason=face_mismatch at {now_str}")
            insert_mismatch_log(sid, "face_mismatch")
            overlay_text = "MISMATCH (Proxy?)"
            overlay_color = (0, 0, 255)
            overlay_time = time.time()
            
        elif status == "CARD_NO_FACE":
            print(f"[PROXY ATTEMPT] card={sid} reason=no_face at {now_str}")
            insert_mismatch_log(sid, "no_face")
            overlay_text = "CARD BUT NO FACE"
            overlay_color = (0, 165, 255)
            overlay_time = time.time()
            
        elif status == "NO_ENCODING":
            print(f"[ERROR] card={sid} reason=unregistered_face at {now_str}")
            overlay_text = "UNKNOWN ID"
            overlay_color = (0, 0, 255)
            overlay_time = time.time()
            
        elif status == "DEBOUNCED":
            overlay_text = "ALREADY LOGGED"
            overlay_color = (255, 255, 0)
            overlay_time = time.time()

        if time.time() - overlay_time > overlay_duration:
            overlay_text = "System Ready"
            overlay_color = (255, 255, 255)
            
        if status == "WAITING":
            draw_overlay(frame, "Waiting for 2nd factor...", (255, 255, 0), qr_points, face_box)
        else:
            draw_overlay(frame, overlay_text, overlay_color, qr_points, face_box)

        cv2.imshow("Smart Lab Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
