import csv
import os
import threading
import time
from datetime import datetime
import cv2
import requests

try:
    import serial
except ImportError:
    serial = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from secrets_config import BOT_TOKEN, CHAT_ID
except ImportError:
    BOT_TOKEN, CHAT_ID = None, None

from telegram_automation import telegram_mgr

# ------------------------- SETTINGS -------------------------
MODEL_PATH = "best.pt"       # Path to YOLO model weights
CAMERA_INDEX = 0             # 0 for default webcam, 1 for external USB
SERIAL_PORT = "COM5"         # Connected to Arduino Uno on COM5
BAUD_RATE = 9600
CONFIDENCE = 0.5             # Detection confidence threshold (0.35 - 0.5)
IMG_SIZE = 640               # 640 standard; set to 480 if video lags
FRAMES_NEEDED = 5            # Consecutive frames with both helmet & vest to pass
MIN_SEEN_FRAMES = 3          # Minimum seen frames to count as present in check window
TRIGGER_CM = 100             # Distance to trigger check (in cm)
LEAVE_CM = 120               # Distance considered as person stepped away (in cm)
HOLD_SEC = 0.6               # Stabilization duration before triggering (avoids spikes)
CHECK_WINDOW_SEC = 3.0       # Timeout window for PPE inspection
GRANT_OPEN_SEC = 17.5        # Full access cycle: 1.10s opening + 15.0s rest at 90 deg + 1.10s closing
DENY_SHOW_SEC = 3.0          # Duration red denied state is displayed
ALERT_COOLDOWN = 40          # Seconds between Telegram violation alerts

HELMET_NAMES = {"hardhat", "helmet", "hard hat", "hard-hat", "safety_helmet", "safety helmet"}
VEST_NAMES = {"safety vest", "safety_vest", "safety-vest", "vest", "reflective vest"}

LOG_FILE = "logs/events.csv"
MINUTE_LOG_FILE = "logs/minute_data.csv"
os.makedirs("logs", exist_ok=True)
os.makedirs("snapshots", exist_ok=True)

# ------------------------- ARDUINO LINK -------------------------
distance_cm = 999
ser = None

if SERIAL_PORT and serial:
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for Arduino reset on port open
        print(f"Connected to Arduino on {SERIAL_PORT}")
    except Exception as e:
        print(f"Warning: Could not connect to Arduino on {SERIAL_PORT} ({e}).")
        print("Falling back to Simulation Mode (keys 'n' and 'f').")
        ser = None
        SERIAL_PORT = None

if ser:
    def read_serial():
        global distance_cm
        while ser and ser.is_open:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if line.startswith("D:"):
                    distance_cm = int(line[2:])
            except ValueError:
                pass
            except Exception:
                break

    threading.Thread(target=read_serial, daemon=True).start()

last_cmd = None

def send(cmd):
    """Send a single-letter command to Arduino (only when changed)."""
    global last_cmd
    if cmd == last_cmd:
        return
    last_cmd = cmd
    if ser and ser.is_open:
        try:
            ser.write(cmd.encode())
        except Exception as e:
            print(f"Serial write error: {e}")
    print("-> Arduino command:", cmd)

# ------------------------- LOGGING AND ALERTS -------------------------
def log_event(result, missing, snapshot=""):
    try:
        new_file = not os.path.exists(LOG_FILE)
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(["timestamp", "result", "missing", "snapshot"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                result,
                "+".join(missing),
                snapshot
            ])
    except PermissionError:
        print("Could not write the log. Close events.csv if open in Excel.")

def save_snapshot(frame):
    path = "snapshots/" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    cv2.imwrite(path, frame)
    return path

def send_telegram_alert(missing, photo_path):
    telegram_mgr.queue_violation_alert(missing, photo_path)

# ------------------------- AI DETECTION -------------------------
model = None
target_class_ids = []
if YOLO is not None and os.path.exists(MODEL_PATH):
    print(f"Loading YOLO model from {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)
    print("Model classes:", model.names)
    for cid, cname in model.names.items():
        c_lower = cname.lower()
        if "mask" not in c_lower and (any(h in c_lower for h in ["hardhat", "helmet"]) or "vest" in c_lower):
            target_class_ids.append(cid)
    print(f"Mask filter removed. Active classes: {[model.names[i] for i in target_class_ids]}")
else:
    if YOLO is None:
        print("Notice: 'ultralytics' not installed. Install via: pip install ultralytics")
    if not os.path.exists(MODEL_PATH):
        print(f"Notice: Model weights '{MODEL_PATH}' not found in folder.")
    print("Running in AI simulation placeholder mode until model weights are placed.")

def detect(frame):
    """Detect PPE items in frame. Returns (helmet_seen, vest_seen, annotated_frame)."""
    if model is not None:
        result = model(frame, imgsz=IMG_SIZE, conf=CONFIDENCE, classes=target_class_ids if target_class_ids else None, verbose=False)[0]
        helmet = vest = False
        for box in result.boxes:
            name = model.names[int(box.cls[0])].lower()
            if name in HELMET_NAMES and not name.startswith("no-"):
                helmet = True
            elif name in VEST_NAMES and not name.startswith("no-"):
                vest = True
        return helmet, vest, result.plot()
    else:
        # Fallback placeholder when model weights not yet downloaded
        cv2.putText(frame, "AI Model: Place best.pt in folder", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        return False, False, frame

# ------------------------- MAIN LOOP -------------------------
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"Cannot open camera index {CAMERA_INDEX}. Trying index 1...")
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        raise SystemExit("Cannot open any camera. Please connect a webcam.")

GREY = (90, 90, 90)
ORANGE = (0, 140, 255)
GREEN = (0, 150, 0)
RED = (0, 0, 200)

state = "IDLE"
state_start = time.time()
near_since = None
far_since = None
streak = 0
helmet_frames = 0
vest_frames = 0

last_minute_refresh = time.time()
MINUTE_INTERVAL = 60.0

send("I")
print("\n--- PPE Compliance Gate System Running ---")
if SERIAL_PORT is None:
    print("SIMULATION MODE ACTIVE:")
    print("  Press 'n' to simulate person standing near (50 cm)")
    print("  Press 'f' to simulate person walking away (200 cm)")
print("  Press 'q' in the camera window to quit.\n")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    now = time.time()
    shown = frame
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    # 1-Minute Periodic Data Storage & System Refresh
    if now - last_minute_refresh >= MINUTE_INTERVAL:
        last_minute_refresh = now
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            new_file = not os.path.exists(MINUTE_LOG_FILE) or os.path.getsize(MINUTE_LOG_FILE) == 0
            with open(MINUTE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow([
                        "timestamp", "state", "distance_cm", "helmet_detected", "vest_detected",
                        "barrier_status", "arduino_status"
                    ])
                writer.writerow([
                    timestamp_str, state, distance_cm,
                    int(helmet_frames > 0), int(vest_frames > 0),
                    "OPEN" if state == "RESULT_PASS" else "CLOSED",
                    "CONNECTED" if ser and ser.is_open else "SIMULATED"
                ])
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp_str, "SYSTEM_REFRESH", f"1-Min Audit: State={state}, Dist={distance_cm}cm", ""])
        except Exception as e:
            print("Minute log error:", e)

        # Refresh system state if idle
        if state in ("IDLE", "WAIT_LEAVE"):
            state = "IDLE"
            streak = helmet_frames = vest_frames = 0
            near_since = far_since = None
            send("I")
        print(f"[{timestamp_str}] [1-MIN REFRESH] Data stored to {MINUTE_LOG_FILE} and system refreshed.")

    # Keyboard simulation for distance if no Arduino connected
    if SERIAL_PORT is None:
        if key == ord("n"):
            distance_cm = 50
            print("[Sim] Person arrived (50 cm)")
        if key == ord("f"):
            distance_cm = 200
            print("[Sim] Person left (200 cm)")

    is_near = distance_cm < TRIGGER_CM
    is_far = distance_cm > LEAVE_CM

    near_since = (near_since or now) if is_near else None
    far_since = (far_since or now) if is_far else None

    near_ok = near_since is not None and (now - near_since >= HOLD_SEC)
    far_ok = far_since is not None and (now - far_since >= HOLD_SEC)

    # State Machine
    if state == "IDLE":
        text, color = "Step closer", GREY
        if near_ok:
            state, state_start = "CHECKING", now
            streak = helmet_frames = vest_frames = 0
            send("C")

    elif state == "CHECKING":
        text, color = "Checking PPE...", ORANGE
        helmet, vest, shown = detect(frame)

        streak = (streak + 1) if (helmet and vest) else 0
        helmet_frames += int(helmet)
        vest_frames += int(vest)

        if streak >= FRAMES_NEEDED:
            send("G")
            log_event("PASS", [])
            state, state_start = "RESULT_PASS", now
        elif far_ok:
            send("I")
            state = "IDLE"
        elif now - state_start > CHECK_WINDOW_SEC:
            missing = []
            if helmet_frames < MIN_SEEN_FRAMES:
                missing.append("helmet")
            if vest_frames < MIN_SEEN_FRAMES:
                missing.append("vest")

            if not missing:
                # Both seen but not in enough consecutive frames: give another window
                state_start = now
                streak = helmet_frames = vest_frames = 0
            else:
                cmd = "R" if len(missing) == 2 else ("H" if "helmet" in missing else "V")
                send(cmd)
                photo = save_snapshot(shown)
                log_event("VIOLATION", missing, photo)
                send_telegram_alert(missing, photo)
                state, state_start = "RESULT_FAIL", now

    elif state == "RESULT_PASS":
        text, color = "ACCESS GRANTED", GREEN
        if now - state_start > GRANT_OPEN_SEC:
            send("I")
            state = "WAIT_LEAVE"

    elif state == "RESULT_FAIL":
        text, color = "ACCESS DENIED", RED
        if now - state_start > DENY_SHOW_SEC:
            send("I")
            state = "WAIT_LEAVE"

    else:  # WAIT_LEAVE
        text, color = "Please step away", GREY
        if far_ok:
            state = "IDLE"

    # Status Banner Overlay
    cv2.rectangle(shown, (0, 0), (shown.shape[1], 40), color, -1)
    status_label = f"{text} | Dist: {distance_cm} cm | State: {state}"
    cv2.putText(shown, status_label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("PPE Compliance Gate (q to quit)", shown)

# Clean up
send("I")
cap.release()
cv2.destroyAllWindows()
if ser:
    ser.close()
print("Program exited cleanly.")

