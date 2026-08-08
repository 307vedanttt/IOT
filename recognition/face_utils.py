"""
face_utils.py — Face Detection & Encoding Helpers
===================================================
"""

import face_recognition
import cv2
import pickle
import os
import numpy as np

EMBEDDINGS_DIR = "../data/embeddings"
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

# We use 0.45 as a stricter tolerance (default is 0.6).
# Since we average 5 faces at enrollment, the resulting enrollment embedding is highly representative.
# A stricter threshold helps prevent false positives (impostor acceptance) in a lab security context.
TOLERANCE = 0.45

def detect_faces(frame: np.ndarray) -> list[tuple]:
    """Return list of face bounding boxes [(top, right, bottom, left), ...] in the frame."""
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return face_recognition.face_locations(rgb_frame)

def encode_face(frame: np.ndarray, face_locations=None) -> np.ndarray | None:
    """Return 128-d encoding for the first face found, or None if no face detected."""
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if face_locations is None:
        face_locations = face_recognition.face_locations(rgb_frame)
        
    if not face_locations:
        return None
        
    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    return encodings[0] if encodings else None

def load_known_encoding(student_id: str) -> np.ndarray | None:
    """Load and return a student's stored face encoding from disk, or None if not found."""
    path = os.path.join(EMBEDDINGS_DIR, f"{student_id}.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)

def save_encoding(student_id: str, encoding: np.ndarray) -> None:
    """Save a face encoding to disk for a given student_id."""
    path = os.path.join(EMBEDDINGS_DIR, f"{student_id}.pkl")
    with open(path, "wb") as f:
        pickle.dump(encoding, f)

def compare(known_encoding: np.ndarray, candidate_encoding: np.ndarray, tolerance=TOLERANCE) -> tuple[bool, float]:
    """
    Return (is_match, confidence)
    Confidence is derived from face distance (lower distance = higher confidence).
    """
    distance = face_recognition.face_distance([known_encoding], candidate_encoding)[0]
    is_match = distance <= tolerance
    
    # Simple confidence metric: distance 0 = 100%, distance at threshold = 50%
    # This is a rough estimation for UI display
    confidence = max(0.0, 1.0 - (distance / (tolerance * 2)))
    
    return is_match, round(confidence * 100, 1)
