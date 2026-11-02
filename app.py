"""
PPE Compliance Gate - Mission Control Web Application
Full-stack IoT & AI Safety Monitoring System with Real-Time Telemetry
"""

import os
import csv
import time
import shutil
import threading
from datetime import datetime, timedelta
from typing import Optional

import cv2
import numpy as np
import requests
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

try:
    import serial
    import serial.tools.list_ports
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

from telegram_automation import telegram_mgr, is_configured as is_telegram_configured

# ------------------------- CONFIGURATION -------------------------
MODEL_PATH = "best.pt"
CONFIDENCE_THRESHOLD = 0.35  # Optimal sensitivity for indoor lighting
IMG_SIZE = 640
CAMERA_INDEX = 0

TRIGGER_CM = 120        # Distance to wake gate into CHECKING
LEAVE_CM = 140          # Distance considered clear
HOLD_SEC = 0.3          # Debounce hold time for distance trigger
CHECK_WINDOW_SEC = 1.2  # Immediate violation window  # Max window to verify both helmet and vest
GRANT_OPEN_SEC = 17.5   # Full access cycle: 1.10s opening + 15.0s rest at 90 deg + 1.10s closing
DENY_SHOW_SEC = 3.0     # Duration violation alert remains active
FRAMES_NEEDED = 2       # Consecutive compliant frames to grant access
MIN_SEEN_FRAMES = 1      # Immediate trigger     # Minimum frames an item must be observed

HELMET_NAMES = {"hardhat", "helmet", "hard hat", "hard-hat", "safety_helmet", "safety helmet"}
VEST_NAMES = {"safety vest", "safety_vest", "safety-vest", "vest", "reflective vest"}

LOG_FILE = "logs/events.csv"
MINUTE_LOG_FILE = "logs/minute_data.csv"
os.makedirs("logs", exist_ok=True)
os.makedirs("snapshots", exist_ok=True)

# ------------------------- SHARED SYSTEM STATE -------------------------
class SystemState:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = "IDLE"           # IDLE, CHECKING, RESULT_PASS, RESULT_FAIL, WAIT_LEAVE
        self.distance_cm = 999
        self.manual_distance: Optional[int] = None
        
        # 1-Minute Refresh and Data Logging
        self.last_minute_refresh = time.time()
        self.minute_refresh_interval = 60.0  # Exactly 60 seconds (1 minute)
        self.minute_records_count = 0
        
        # Hardware indicators
        self.barrier_open = False
        self.green_led = False
        self.red_led = False
        self.buzzer = False
        
        # Live Detection Metrics
        self.helmet_detected = False
        self.vest_detected = False
        self.person_detected = False
        self.person_frames = 0
        self.helmet_conf = 0.0
        self.vest_conf = 0.0
        self.missing_items = []
        
        # LCD Display Mirror
        self.lcd_line1 = "PPE Gate"
        self.lcd_line2 = "Step closer"
        
        # Serial Transaction Log
        self.serial_log = [
            {"time": datetime.now().strftime("%H:%M:%S"), "dir": "RX", "text": "System booted. Waiting for Arduino..."}
        ]
        
        # Timers & streaks
        self.state_start = time.time()
        self.near_since = None
        self.far_since = None
        self.streak = 0
        self.helmet_frames = 0
        self.vest_frames = 0
        
        # Arduino Link
        self.arduino_connected = False
        self.arduino_port = "Auto-searching..."
        self.last_sent_cmd = None
        
        # Latest frame & telemetry
        self.latest_jpeg = None
        self.fps = 0

sys_state = SystemState()
arduino_ser = None
last_alert_time = 0

# ------------------------- ARDUINO AUTO-LINK THREAD -------------------------
def send_arduino(cmd: str):
    """Send single-character command to Arduino and update live LCD mirror."""
    global arduino_ser
    with sys_state.lock:
        if sys_state.last_sent_cmd == cmd:
            return
        sys_state.last_sent_cmd = cmd
        
        lcd_map = {
            "I": ("PPE Gate", "Step closer"),
            "C": ("Checking PPE", "Hold still..."),
            "G": ("ACCESS GRANTED", "Please enter"),
            "R": ("ACCESS DENIED", "No helmet+vest"),
            "H": ("ACCESS DENIED", "Missing: HELMET"),
            "V": ("ACCESS DENIED", "Missing: VEST"),
        }
        l1, l2 = lcd_map.get(cmd, ("PPE Gate", "Step closer"))
        sys_state.lcd_line1 = l1
        sys_state.lcd_line2 = l2
        
        # Mirror virtual hardware states
        if cmd == "I":
            sys_state.barrier_open = False
            sys_state.green_led = False
            sys_state.red_led = False
            sys_state.buzzer = False
        elif cmd == "C":
            sys_state.barrier_open = False
            sys_state.green_led = False
            sys_state.red_led = False
            sys_state.buzzer = False
        elif cmd == "G":
            sys_state.barrier_open = True
            sys_state.green_led = True
            sys_state.red_led = False
            sys_state.buzzer = False
        elif cmd in ("R", "H", "V"):
            sys_state.barrier_open = False
            sys_state.green_led = False
            sys_state.red_led = True
            sys_state.buzzer = True

        log_entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "dir": "TX",
            "text": f"Cmd '{cmd}' -> {l1}"
        }
        sys_state.serial_log.append(log_entry)
        if len(sys_state.serial_log) > 15:
            sys_state.serial_log.pop(0)

    if arduino_ser and arduino_ser.is_open:
        try:
            arduino_ser.write(cmd.encode())
            print(f"-> Arduino: {cmd}")
        except Exception as e:
            print(f"Arduino send error: {e}")

def arduino_manager():
    """Continuously monitors and auto-connects to Arduino Uno on USB."""
    global arduino_ser
    while True:
        if not sys_state.arduino_connected:
            ports = list(serial.tools.list_ports.comports()) if serial else []
            candidate = None
            
            for p in ports:
                desc = p.description.lower()
                if "bluetooth" in desc:
                    continue
                if p.device == "COM5" or "serial" in desc or "ch340" in desc or "ftdi" in desc or "arduino" in desc or "usb" in desc:
                    candidate = p.device
                    break
            if not candidate and ports:
                for p in ports:
                    if "bluetooth" not in p.description.lower():
                        candidate = p.device
                        break
            
            if candidate:
                try:
                    s = serial.Serial(candidate, 9600, timeout=1)
                    time.sleep(2)
                    arduino_ser = s
                    with sys_state.lock:
                        sys_state.arduino_connected = True
                        sys_state.arduino_port = candidate
                        sys_state.serial_log.append({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "dir": "SYS",
                            "text": f"Connected to Arduino on {candidate} (9600 baud)"
                        })
                    print(f"Auto-connected to Arduino on {candidate}")
                    send_arduino("I")
                except Exception:
                    pass
            
            if not sys_state.arduino_connected:
                with sys_state.lock:
                    sys_state.arduino_port = "Auto-searching..."
                time.sleep(2)
                continue
        
        # Read distance stream
        try:
            if arduino_ser and arduino_ser.is_open:
                line = arduino_ser.readline().decode(errors="ignore").strip()
                if line.startswith("D:"):
                    try:
                        cm = int(line[2:])
                        with sys_state.lock:
                            if sys_state.manual_distance is None:
                                sys_state.distance_cm = cm
                    except ValueError:
                        pass
        except Exception as e:
            print(f"Arduino connection lost ({e}). Re-scanning...")
            with sys_state.lock:
                sys_state.arduino_connected = False
                sys_state.serial_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "dir": "SYS",
                    "text": "Connection lost. Re-scanning USB ports..."
                })
            if arduino_ser:
                try:
                    arduino_ser.close()
                except Exception:
                    pass
            time.sleep(1)

# ------------------------- LOGGING & ALERTS -------------------------
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
    except Exception as e:
        print(f"Log write error: {e}")

def save_snapshot(frame):
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    path = os.path.join("snapshots", filename)
    cv2.imwrite(path, frame)
    return path

def send_telegram(missing, photo_path):
    """Dispatches asynchronous formatted Telegram photo alert with rate-limiting."""
    telegram_mgr.queue_violation_alert(missing, photo_path)

def get_current_snapshot_bytes():
    """Provides latest live webcam frame bytes for Telegram /snapshot command."""
    with sys_state.lock:
        return sys_state.latest_jpeg

telegram_mgr.snapshot_provider = get_current_snapshot_bytes

def handle_telegram_command(cmd, arg):
    """Executes interactive 2-way Telegram commands from the bot chat."""
    if cmd == "open":
        override_open()
        return "Barrier opened for 15s entry hold"
    elif cmd == "close":
        override_close()
        return "Closed"
    elif cmd == "status":
        with sys_state.lock:
            st = sys_state.state
            dist = sys_state.distance_cm if sys_state.manual_distance is None else sys_state.manual_distance
            ard = f"Connected ({sys_state.arduino_port})" if sys_state.arduino_connected else "Disconnected"
            b = "OPEN (90°)" if sys_state.barrier_open else "CLOSED (0°)"
        stats = get_stats()
        return (
            f"📊 <b>PPE Compliance Gate — Real-Time Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Gate State:</b> <code>{st}</code>\n"
            f"• <b>Proximity:</b> <code>{dist} cm</code>\n"
            f"• <b>Barrier Servo:</b> <b>{b}</b>\n"
            f"• <b>Arduino Link:</b> {ard}\n"
            f"• <b>Compliance Rate:</b> <b>{stats.get('rate', 0)}%</b>\n"
            f"• <b>Total Entries:</b> {stats.get('total', 0)} (Passed: {stats.get('pass', 0)}, Denied: {stats.get('fail', 0)})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )
    elif cmd == "stats":
        stats = get_stats()
        return (
            f"📈 <b>PPE Audit Statistics</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Total Scans:</b> {stats.get('total', 0)}\n"
            f"• <b>Compliant (Passed):</b> {stats.get('pass', 0)}\n"
            f"• <b>Violations (Denied):</b> {stats.get('fail', 0)}\n"
            f"• <b>Compliance Rate:</b> <b>{stats.get('rate', 0)}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    return "OK"

telegram_mgr.command_handler = handle_telegram_command

# ------------------------- VISION & STATE MACHINE WORKER -------------------------
def vision_worker():
    """Runs camera capture, YOLO detection, and state machine continuously."""
    print("Initializing YOLO model...")
    model = None
    if YOLO and os.path.exists(MODEL_PATH):
        try:
            model = YOLO(MODEL_PATH)
            print("YOLO model loaded successfully.")
        except Exception as e:
            print(f"Could not load YOLO: {e}")

    target_class_ids = []
    if model is not None:
        for cid, cname in model.names.items():
            c_lower = cname.lower()
            if "mask" not in c_lower and (any(h in c_lower for h in ["hardhat", "helmet"]) or "vest" in c_lower or "person" in c_lower):
                target_class_ids.append(cid)
        print(f"Mask filter removed. Active classes: {[model.names[i] for i in target_class_ids]}")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)

    fps_counter = 0
    fps_timer = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Initializing Camera...", (160, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 180, 255), 2)
            frame = blank
            time.sleep(0.04)

        now = time.time()
        fps_counter += 1
        if now - fps_timer >= 1.0:
            with sys_state.lock:
                sys_state.fps = fps_counter
            fps_counter = 0
            fps_timer = now

        # Run AI Detection (Detect Person, Helmet, Vest and NO-PPE classes)
        helmet_seen = False
        vest_seen = False
        person_seen = False
        no_helmet_seen = False
        no_vest_seen = False
        max_h_conf = 0.0
        max_v_conf = 0.0
        annotated_frame = frame.copy()

        if model is not None:
            results = model(
                frame,
                imgsz=IMG_SIZE,
                conf=CONFIDENCE_THRESHOLD,
                classes=target_class_ids if target_class_ids else None,
                verbose=False
            )[0]
            annotated_frame = results.plot()
            for box in results.boxes:
                name = model.names[int(box.cls[0])].lower()
                conf = float(box.conf[0])
                if "person" in name:
                    person_seen = True
                elif "no-hardhat" in name or "no-helmet" in name:
                    no_helmet_seen = True
                    person_seen = True
                elif "no-safety vest" in name or "no-vest" in name:
                    no_vest_seen = True
                    person_seen = True
                elif name in HELMET_NAMES and not name.startswith("no-"):
                    helmet_seen = True
                    person_seen = True
                    if conf > max_h_conf:
                        max_h_conf = conf
                elif name in VEST_NAMES and not name.startswith("no-"):
                    vest_seen = True
                    person_seen = True
                    if conf > max_v_conf:
                        max_v_conf = conf

        with sys_state.lock:
            sys_state.helmet_detected = helmet_seen
            sys_state.vest_detected = vest_seen
            sys_state.person_detected = person_seen
            sys_state.helmet_conf = round(max_h_conf * 100, 1)
            sys_state.vest_conf = round(max_v_conf * 100, 1)

            current_dist = sys_state.distance_cm if sys_state.manual_distance is None else sys_state.manual_distance
            current_state = sys_state.state

            is_near = current_dist < TRIGGER_CM
            is_far = current_dist > LEAVE_CM

            sys_state.near_since = (sys_state.near_since or now) if is_near else None
            sys_state.far_since = (sys_state.far_since or now) if is_far else None

            near_ok = sys_state.near_since is not None and (now - sys_state.near_since >= HOLD_SEC)
            far_ok = sys_state.far_since is not None and (now - sys_state.far_since >= HOLD_SEC)

            # State Transitions
            if current_state == "IDLE":
                # Only enter CHECKING if a person is near or detected
                if (near_ok and person_seen) or (helmet_seen and vest_seen) or (person_seen and (no_helmet_seen or no_vest_seen)):
                    sys_state.state = "CHECKING"
                    sys_state.state_start = now
                    sys_state.streak = 0
                    sys_state.helmet_frames = 0
                    sys_state.vest_frames = 0
                    sys_state.person_frames = 0
                    send_arduino("C")
                elif near_ok and not person_seen:
                    # Non-human proximity or background fluctuation -> remain IDLE
                    pass

            elif current_state == "CHECKING":
                sys_state.person_frames += int(person_seen)

                if helmet_seen and vest_seen:
                    sys_state.streak += 1
                else:
                    sys_state.streak = 0

                sys_state.helmet_frames += int(helmet_seen)
                sys_state.vest_frames += int(vest_seen)

                # Instant Opening when both gear items verified (Person is wearing PPE kit)
                if sys_state.streak >= FRAMES_NEEDED or (sys_state.helmet_frames >= 2 and sys_state.vest_frames >= 2):
                    send_arduino("G")
                    log_event("PASS", [])
                    sys_state.state = "RESULT_PASS"
                    sys_state.state_start = now
                elif far_ok and not (person_seen or helmet_seen or vest_seen):
                    send_arduino("I")
                    sys_state.state = "IDLE"
                elif now - sys_state.state_start > CHECK_WINDOW_SEC:
                    # Evaluation window expired -> Verify human presence
                    person_present = (sys_state.person_frames >= 1 or person_seen or no_helmet_seen or no_vest_seen)
                    
                    if not person_present:
                        # False trigger (no person in frame) -> silently return to IDLE without violation
                        send_arduino("I")
                        sys_state.state = "IDLE"
                    else:
                        # Person is present but NOT wearing required PPE kit!
                        missing = []
                        if sys_state.helmet_frames < MIN_SEEN_FRAMES or no_helmet_seen:
                            missing.append("helmet")
                        if sys_state.vest_frames < MIN_SEEN_FRAMES or no_vest_seen:
                            missing.append("vest")

                        if not missing:
                            send_arduino("G")
                            log_event("PASS", [])
                            sys_state.state = "RESULT_PASS"
                            sys_state.state_start = now
                        else:
                            # Trigger violation: person is NOT wearing PPE kit (dispatches Telegram alert with 40s rate-limit)
                            cmd = "R" if len(missing) == 2 else ("H" if "helmet" in missing else "V")
                            send_arduino(cmd)
                            snap = save_snapshot(annotated_frame)
                            log_event("VIOLATION", missing, snap)
                            send_telegram(missing, snap)
                            sys_state.missing_items = missing
                            sys_state.state = "RESULT_FAIL"
                            sys_state.state_start = now

            elif current_state == "RESULT_PASS":
                if now - sys_state.state_start > GRANT_OPEN_SEC:
                    send_arduino("I")
                    sys_state.state = "WAIT_LEAVE"

            elif current_state == "RESULT_FAIL":
                if now - sys_state.state_start > DENY_SHOW_SEC:
                    send_arduino("I")
                    sys_state.state = "WAIT_LEAVE"

            elif current_state == "WAIT_LEAVE":
                if far_ok:
                    send_arduino("I")
                    sys_state.state = "IDLE"

            banner_colors = {
                "IDLE": (70, 70, 70),
                "CHECKING": (0, 140, 255),
                "RESULT_PASS": (0, 160, 40),
                "RESULT_FAIL": (30, 30, 220),
                "WAIT_LEAVE": (90, 90, 90)
            }
            color = banner_colors.get(sys_state.state, (70, 70, 70))
            current_st = sys_state.state

        # Encode clean frame without HUD banner box
        ret, jpeg = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ret:
            with sys_state.lock:
                sys_state.latest_jpeg = jpeg.tobytes()

        time.sleep(0.01)

# ------------------------- FASTAPI SERVER & UI -------------------------
app = FastAPI(title="PPE Compliance Gate Mission Control")
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_stats(range_filter: str = "today"):
    if not os.path.exists(LOG_FILE):
        return {
            "total": 0, "pass": 0, "fail": 0, "rate": 0,
            "missing_helmet": 0, "missing_vest": 0,
            "hourly": [], "peak_hour": "--:--", "events": [], "violations": []
        }
    events = []
    total = pass_cnt = fail_cnt = 0
    h_miss = v_miss = 0
    from collections import defaultdict
    now = datetime.now()
    
    # 12-hour slots for the hourly chart
    hours = []
    hour_counts = defaultdict(lambda: {"pass": 0, "fail": 0})
    for i in range(11, -1, -1):
        h_time = now - timedelta(hours=i) if 'timedelta' in globals() else now
        h_str = (now - timedelta(hours=i)).strftime("%H:00")
        hours.append(h_str)

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            res = row.get("result")
            if res in ("PASS", "VIOLATION"):
                events.append(row)
                total += 1
                if res == "PASS":
                    pass_cnt += 1
                elif res == "VIOLATION":
                    fail_cnt += 1
                
                # Missing gear analysis
                miss_str = str(row.get("missing", "")).lower()
                if "helmet" in miss_str:
                    h_miss += 1
                if "vest" in miss_str:
                    v_miss += 1
                
                # Hourly bucket
                try:
                    ts = row.get("timestamp", "")
                    if len(ts) >= 13:
                        dt = datetime.strptime(ts[:13], "%Y-%m-%d %H")
                        h_str = dt.strftime("%H:00")
                        if res == "PASS":
                            hour_counts[h_str]["pass"] += 1
                        elif res == "VIOLATION":
                            hour_counts[h_str]["fail"] += 1
                except Exception:
                    pass

    rate = round((pass_cnt / total * 100), 1) if total else 0
    hourly_data = [{"hour": h, "pass": hour_counts[h]["pass"], "fail": hour_counts[h]["fail"]} for h in hours]
    
    # Peak hour computation
    peak_h = "--:--"
    if hour_counts:
        peak_entry = max(hour_counts.items(), key=lambda item: item[1]["fail"])
        if peak_entry[1]["fail"] > 0:
            peak_h = f"{peak_entry[0]}"

    # Violations list with photos for /reports
    violations = [e for e in events if e.get("result") == "VIOLATION"]
    violations.reverse()

    return {
        "total": total,
        "pass": pass_cnt,
        "fail": fail_cnt,
        "rate": rate,
        "missing_helmet": h_miss,
        "missing_vest": v_miss,
        "hourly": hourly_data,
        "peak_hour": peak_h,
        "events": events[-60:][::-1],
        "violations": violations
    }

def get_minute_stats():
    """Reads latest 10 rows from logs/minute_data.csv for live dashboard display."""
    if not os.path.exists(MINUTE_LOG_FILE):
        return []
    rows = []
    try:
        with open(MINUTE_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return rows[-10:][::-1]

def log_minute_data_and_refresh(force: bool = False):
    """
    Called every 60 seconds (1 minute):
    1. Stores snapshot of telemetry, detection metrics, & compliance rates to logs/minute_data.csv.
    2. Logs a periodic heartbeat row to logs/events.csv.
    3. Refreshes the system: clears streaks/timers, resets stuck states,
       and sends 'I' to Arduino to guarantee closed barrier (0 deg) & standby LCD.
    """
    now = time.time()
    with sys_state.lock:
        if not force and (now - sys_state.last_minute_refresh < sys_state.minute_refresh_interval):
            return
        sys_state.last_minute_refresh = now
        
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        curr_state = sys_state.state
        dist = sys_state.distance_cm if sys_state.manual_distance is None else sys_state.manual_distance
        h_seen = 1 if sys_state.helmet_detected else 0
        v_seen = 1 if sys_state.vest_detected else 0
        h_conf = sys_state.helmet_conf
        v_conf = sys_state.vest_conf
        barrier = "OPEN" if sys_state.barrier_open else "CLOSED"
        g_led = "ON" if sys_state.green_led else "OFF"
        r_led = "ON" if sys_state.red_led else "OFF"
        buzz = "ON" if sys_state.buzzer else "OFF"
        ard_conn = "CONNECTED" if sys_state.arduino_connected else "DISCONNECTED"

    # Get latest statistics
    stats = get_stats()
    total_checks = stats.get("total", 0)
    passed_checks = stats.get("pass", 0)
    failed_checks = stats.get("fail", 0)
    compliance_rate = stats.get("rate", 0.0)

    # 1. Store in logs/minute_data.csv
    try:
        new_file = not os.path.exists(MINUTE_LOG_FILE) or os.path.getsize(MINUTE_LOG_FILE) == 0
        with open(MINUTE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow([
                    "timestamp", "state", "distance_cm", "helmet_detected", "vest_detected",
                    "helmet_conf", "vest_conf", "barrier_status", "green_led", "red_led",
                    "buzzer", "arduino_status", "total_checks", "passed", "violations", "compliance_rate"
                ])
            writer.writerow([
                timestamp_str, curr_state, dist, h_seen, v_seen,
                h_conf, v_conf, barrier, g_led, r_led,
                buzz, ard_conn, total_checks, passed_checks, failed_checks, compliance_rate
            ])
    except Exception as e:
        print(f"Error saving minute_data.csv: {e}")

    # 2. Append heartbeat entry in logs/events.csv
    try:
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp_str,
                "SYSTEM_REFRESH",
                f"1-Min Audit: State={curr_state}, Rate={compliance_rate}%",
                ""
            ])
    except Exception as e:
        print(f"Error logging heartbeat to events.csv: {e}")

    # 3. Perform System Refresh
    with sys_state.lock:
        sys_state.minute_records_count += 1
        # If in idle or stuck waiting, reset to clean IDLE state
        if sys_state.state in ("IDLE", "WAIT_LEAVE") or (now - sys_state.state_start > 15.0):
            sys_state.state = "IDLE"
            sys_state.streak = 0
            sys_state.helmet_frames = 0
            sys_state.vest_frames = 0
            sys_state.near_since = None
            sys_state.far_since = None
            sys_state.manual_distance = None  # Return to live ultrasonic sensor

        # Add event to live serial terminal
        log_entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "dir": "SYS",
            "text": f"1-Min Refresh: Data stored (#{sys_state.minute_records_count}) & system refreshed."
        }
        sys_state.serial_log.append(log_entry)
        if len(sys_state.serial_log) > 15:
            sys_state.serial_log.pop(0)

    # Re-send 'I' to Arduino to ensure physical gate is closed and LCD ready
    if curr_state in ("IDLE", "WAIT_LEAVE"):
        send_arduino("I")
    print(f"[{timestamp_str}] [1-MIN REFRESH] Data stored to {MINUTE_LOG_FILE} and system refreshed.")

def minute_worker():
    """Background worker thread executing 1-minute data logging and system refresh."""
    time.sleep(5)  # 5s startup delay
    while True:
        log_minute_data_and_refresh()
        time.sleep(1)

@app.get("/", response_class=HTMLResponse)
def index():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f_html:
            return f_html.read()
    return '<h1>Sentinel Console - Template not found</h1>'

def gen_frames():
    """Video streaming generator yielding JPEG frames."""
    while True:
        with sys_state.lock:
            jpeg = sys_state.latest_jpeg
        if jpeg is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
        time.sleep(0.03)

@app.get("/video_feed")
@app.get("/stream")
@app.get("/api/stream")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/status")
def api_status():
    snapshots = [f for f in os.listdir("snapshots") if f.endswith(".jpg")]
    snapshots.sort(reverse=True)
    with sys_state.lock:
        return {
            "arduino_connected": sys_state.arduino_connected,
            "arduino_port": sys_state.arduino_port,
            "state": sys_state.state,
            "distance_cm": sys_state.distance_cm if sys_state.manual_distance is None else sys_state.manual_distance,
            "barrier_open": sys_state.barrier_open,
            "green_led": sys_state.green_led,
            "red_led": sys_state.red_led,
            "buzzer": sys_state.buzzer,
            "helmet_detected": sys_state.helmet_detected,
            "vest_detected": sys_state.vest_detected,
            "helmet_conf": sys_state.helmet_conf,
            "vest_conf": sys_state.vest_conf,
            "streak": sys_state.streak,
            "frames_needed": FRAMES_NEEDED,
            "lcd_line1": sys_state.lcd_line1,
            "lcd_line2": sys_state.lcd_line2,
            "serial_log": sys_state.serial_log,
            "fps": sys_state.fps,
            "stats": get_stats(),
            "recent_snapshots": snapshots[:4],
            "next_refresh_sec": max(0, int(sys_state.minute_refresh_interval - (time.time() - sys_state.last_minute_refresh))),
            "minute_records_count": sys_state.minute_records_count,
            "recent_minute_logs": get_minute_stats(),
            "telegram_configured": is_telegram_configured(),
            "telegram_bot": telegram_mgr.bot_username
        }

@app.post("/api/refresh")
def api_refresh():
    log_minute_data_and_refresh(force=True)
    return {"status": "ok", "message": "System refreshed and 1-minute data stored"}

@app.post("/api/telegram/test")
def api_telegram_test():
    ok, msg = telegram_mgr.test_connection()
    if not ok:
        return {"status": "error", "message": msg}
    
    t_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    sent = telegram_mgr.send_text(
        f"✅ <b>PPE Gate System — Telegram Automation Test</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• Status: <b>Online & Verified</b>\n"
        f"• Timestamp: {t_str}\n"
        f"• Connected Port: COM5\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Automated alert test from Mission Control</i>"
    )
    if sent:
        return {"status": "ok", "message": f"Test alert successfully sent to Telegram! ({msg})"}
    return {"status": "error", "message": "Failed to deliver message to Telegram chat. Make sure you pressed Start in your bot chat."}

@app.post("/api/override/open")
def override_open():
    with sys_state.lock:
        sys_state.state = "RESULT_PASS"
        sys_state.state_start = time.time()
        sys_state.barrier_open = True
        sys_state.green_led = True
        sys_state.red_led = False
        sys_state.buzzer = False
        send_arduino("G")
    return {"status": "ok", "action": "open"}

@app.post("/api/override/close")
def override_close():
    with sys_state.lock:
        sys_state.state = "IDLE"
        sys_state.barrier_open = False
        sys_state.green_led = False
        sys_state.red_led = False
        send_arduino("I")
    return {"status": "ok", "action": "close"}

@app.post("/api/simulate/near")
def simulate_near():
    with sys_state.lock:
        sys_state.manual_distance = 50
    return {"status": "ok", "distance": 50}

@app.post("/api/simulate/far")
def simulate_far():
    with sys_state.lock:
        sys_state.manual_distance = 200
    return {"status": "ok", "distance": 200}

@app.post("/api/simulate/pass")
def simulate_pass():
    now = time.time()
    with sys_state.lock:
        sys_state.state = "RESULT_PASS"
        sys_state.state_start = now
        sys_state.barrier_open = True
        sys_state.green_led = True
        sys_state.red_led = False
        sys_state.buzzer = False
        sys_state.helmet_detected = True
        sys_state.vest_detected = True
        sys_state.helmet_conf = 96.5
        sys_state.vest_conf = 94.2
        sys_state.manual_distance = 45
        sys_state.missing_items = []
        send_arduino("G")
    log_event("PASS", [])
    return {"status": "ok", "verdict": "PASS", "message": "Simulated compliant entry (Gate open 15s)"}

@app.post("/api/simulate/violation")
def simulate_violation():
    now = time.time()
    missing = ["helmet"]
    snap = ""
    with sys_state.lock:
        sys_state.state = "RESULT_FAIL"
        sys_state.state_start = now
        sys_state.barrier_open = False
        sys_state.green_led = False
        sys_state.red_led = True
        sys_state.buzzer = True
        sys_state.helmet_detected = False
        sys_state.vest_detected = True
        sys_state.helmet_conf = 0.0
        sys_state.vest_conf = 92.0
        sys_state.manual_distance = 40
        sys_state.missing_items = missing
        send_arduino("H")
        if sys_state.latest_jpeg:
            try:
                import numpy as np
                nparr = np.frombuffer(sys_state.latest_jpeg, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is not None:
                    snap = save_snapshot(frame)
            except Exception:
                pass
    log_event("VIOLATION", missing, snap)
    send_telegram(missing, snap)
    return {"status": "ok", "verdict": "VIOLATION", "missing": missing, "snapshot": snap}

# ------------------------- STARTUP & ENTRYPOINT -------------------------
@app.on_event("startup")
def startup():
    t_arduino = threading.Thread(target=arduino_manager, daemon=True)
    t_arduino.start()

    t_vision = threading.Thread(target=vision_worker, daemon=True)
    t_vision.start()

    t_minute = threading.Thread(target=minute_worker, daemon=True)
    t_minute.start()


@app.get("/reports", response_class=HTMLResponse)
def page_reports():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'reports.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return index()

@app.get("/events", response_class=HTMLResponse)
def page_events():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'events.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return index()

@app.get("/settings", response_class=HTMLResponse)
def page_settings():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'settings.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return index()

@app.get("/about", response_class=HTMLResponse)
def page_about():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'about.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return index()

@app.get("/api/events")
def api_events():
    stats = get_stats()
    return stats.get("events", [])

@app.get("/api/stats")
def api_stats():
    return get_stats()

@app.get("/api/export/csv")
def api_export_csv():
    if os.path.exists(LOG_FILE):
        return FileResponse(LOG_FILE, filename="ppe_checkpoint_events.csv", media_type="text/csv")
    return Response(content="timestamp,result,missing,snapshot\n", media_type="text/csv")

@app.get("/api/settings")
def api_get_settings():
    return {
        "confidence": CONFIDENCE_THRESHOLD,
        "frames_needed": FRAMES_NEEDED,
        "grant_open_sec": GRANT_OPEN_SEC,
        "deny_show_sec": DENY_SHOW_SEC,
        "telegram_cooldown_sec": getattr(telegram_mgr, 'cooldown_sec', 40.0),
        "snapshot_retention": 7,
        "serial_port": "COM5",
        "baud_rate": 9600,
        "telegram_bot": telegram_mgr.bot_username if hasattr(telegram_mgr, 'bot_username') else "@Construction_Safety_Alerts_Bot"
    }

@app.post("/api/clear_log")
def api_clear_log():
    try:
        if os.path.exists(LOG_FILE):
            backup_path = LOG_FILE + f".bak_{int(time.time())}"
            shutil.copyfile(LOG_FILE, backup_path)
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("timestamp,result,missing,snapshot\n")
        return {"status": "ok", "message": "Log cleared and backed up successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/settings")
def api_save_settings(data: dict):
    global CONFIDENCE_THRESHOLD, FRAMES_NEEDED, GRANT_OPEN_SEC, DENY_SHOW_SEC
    if "confidence" in data:
        CONFIDENCE_THRESHOLD = float(data["confidence"])
    if "frames_needed" in data:
        FRAMES_NEEDED = int(data["frames_needed"])
    if "grant_open_sec" in data:
        GRANT_OPEN_SEC = float(data["grant_open_sec"])
    if "deny_show_sec" in data:
        DENY_SHOW_SEC = float(data["deny_show_sec"])
    if "telegram_cooldown_sec" in data and hasattr(telegram_mgr, "cooldown_sec"):
        telegram_mgr.cooldown_sec = float(data["telegram_cooldown_sec"])
    return {"status": "ok", "message": "Settings updated successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
