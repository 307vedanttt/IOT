"""
matcher.py — Dual-Factor Card + Face Cross-Match Logic
=======================================================
"""

import time
from face_utils import load_known_encoding, compare
import numpy as np

DEBOUNCE_SECONDS = 30      # 30-second cooldown window after successful match
RETRY_WINDOW_SECONDS = 5   # wait up to 5 seconds for missing factor

# In-memory state
_last_logged: dict[str, float] = {}   # student_id → timestamp of last log
_pending: dict = {}                   # {student_id: {"timestamp": float, "factor": "QR"|"FACE"}}
_face_mismatch_counter: dict[str, int] = {} # card_id -> consecutive mismatch count

def _clean_pending():
    """Remove pending entries older than RETRY_WINDOW_SECONDS."""
    now = time.time()
    expired = [k for k, v in _pending.items() if now - v["timestamp"] > RETRY_WINDOW_SECONDS]
    for k in expired:
        del _pending[k]

def verify(qr_student_id: str | None, face_encoding: np.ndarray | None) -> tuple[str, str | None]:
    """
    State machine for matching.
    Returns: (STATUS, related_student_id_if_any)
    STATUS codes:
        "MATCH"             - Attendance logged
        "MISMATCH"          - Face doesn't match card (after 2 attempts)
        "CARD_NO_FACE"      - Timeout waiting for face
        "FACE_NO_CARD"      - Handled silently in main loop
        "DEBOUNCED"         - Ignored, matched recently
        "WAITING"           - Waiting for second factor
        "NO_ENCODING"       - Card scanned but no face enrolled
    """
    now = time.time()
    _clean_pending()

    # 1. Neither detected
    if not qr_student_id and face_encoding is None:
        return ("NONE", None)

    # 2. Both detected in same frame
    if qr_student_id and face_encoding is not None:
        return _evaluate_match(qr_student_id, face_encoding, now)

    # 3. Only QR detected
    if qr_student_id and face_encoding is None:
        if qr_student_id in _last_logged and (now - _last_logged[qr_student_id] < DEBOUNCE_SECONDS):
            return ("DEBOUNCED", qr_student_id)
            
        if qr_student_id not in _pending:
            _pending[qr_student_id] = {"timestamp": now, "factor": "QR"}
            return ("WAITING", qr_student_id)
            
        # If pending and expired
        if now - _pending[qr_student_id]["timestamp"] > RETRY_WINDOW_SECONDS:
            del _pending[qr_student_id]
            return ("CARD_NO_FACE", qr_student_id)
            
        return ("WAITING", qr_student_id)

    # 4. Only Face detected (can't map to a student ID yet)
    if face_encoding is not None and not qr_student_id:
        return ("FACE_NO_CARD", None)

    return ("NONE", None)

def _evaluate_match(student_id: str, face_encoding: np.ndarray, now: float) -> tuple[str, str]:
    """Evaluate actual match with retry and debounce."""
    if student_id in _last_logged and (now - _last_logged[student_id] < DEBOUNCE_SECONDS):
        return ("DEBOUNCED", student_id)

    known_enc = load_known_encoding(student_id)
    if known_enc is None:
        return ("NO_ENCODING", student_id)

    is_match, conf = compare(known_enc, face_encoding)
    
    if is_match:
        _last_logged[student_id] = now
        if student_id in _pending:
            del _pending[student_id]
        if student_id in _face_mismatch_counter:
            del _face_mismatch_counter[student_id]
        return ("MATCH", student_id)
    else:
        # Retry logic: require 2 consecutive mismatch evaluations
        count = _face_mismatch_counter.get(student_id, 0) + 1
        _face_mismatch_counter[student_id] = count
        if count >= 2:
            _face_mismatch_counter[student_id] = 0
            if student_id in _pending:
                del _pending[student_id]
            return ("MISMATCH", student_id)
        else:
            # First attempt failed, give it another frame
            return ("WAITING", student_id)
