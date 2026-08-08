"""
qr_utils.py — QR Code Detection & Decoding Helpers
====================================================
"""

import cv2
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

# Initialize OpenCV QR detector once
qr_detector = cv2.QRCodeDetector()

def _parse_qr_payload(raw_text: str) -> str:
    """Extract the student_id from raw QR text."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    if text.startswith("student_id:"):
        return text.split("student_id:")[1]
    return text

def detect_qr(frame) -> dict | None:
    """
    Attempt to detect and decode a QR code in the given frame.
    Returns a dict {'student_id': str, 'points': array} or None if nothing found.
    Tries OpenCV first, falls back to pyzbar.
    """
    # 1. Try OpenCV
    text, points, _ = qr_detector.detectAndDecode(frame)
    if text and points is not None:
        student_id = _parse_qr_payload(text)
        if student_id:
            return {'student_id': student_id, 'points': points.astype(int)}

    # 2. Fallback to pyzbar if available
    if PYZBAR_AVAILABLE:
        # Convert to grayscale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        for barcode in barcodes:
            text = barcode.data.decode("utf-8")
            student_id = _parse_qr_payload(text)
            if student_id:
                # pyzbar points format
                pts = barcode.polygon
                if pts and len(pts) == 4:
                    points_arr = [[pt.x, pt.y] for pt in pts]
                    import numpy as np
                    return {'student_id': student_id, 'points': np.array([points_arr], dtype=int)}
                else:
                    # bounding box fallback
                    x, y, w, h = barcode.rect
                    points_arr = [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]
                    import numpy as np
                    return {'student_id': student_id, 'points': np.array([points_arr], dtype=int)}

    return None

def draw_qr_box(frame, points) -> None:
    """Draw a green polygon on the frame around the detected QR code region."""
    if points is not None:
        cv2.polylines(frame, points, isClosed=True, color=(0,255,0), thickness=2)
