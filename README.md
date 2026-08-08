# Smart Lab Attendance System

A camera-based lab attendance system that identifies students using TWO factors simultaneously: a QR Code on their ID card, and Face Recognition. Attendance is only logged if both factors match, virtually eliminating proxy attendance. The system operates offline via a local SQLite database and automatically syncs to a Firebase Realtime Database cloud dashboard whenever an internet connection is available.

## Known Limitations (Project Scope)
- **Software-Based Entry/Exit**: Entry and exit logs are determined by software toggle logic (first scan = entry, next = exit), not by physical turnstiles or IR beam-break sensors.
- **Simulated Hardware layer**: A separate physical/simulated circuit (built in Tinkercad with IR sensors, gas/temp sensors, and LEDs) exists for this project but is deliberately not physically wired to this software stack. Safety sensor data on the dashboard is meant to be inserted manually to simulate the circuit's output.
- **Single-Lab Scope**: The current database schema and dashboard are scoped to a single lab (`lab_1`).

---

## 1. Environment Setup

Create and activate a Python virtual environment:
```bash
cd recognition
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

> **Note on Dependencies:** `face_recognition` requires `dlib` (which needs CMake and C++ build tools installed on your OS). `pyzbar` requires the `zbar` shared library installed on your system.

## 2. Firebase Configuration

### For the Python Backend (Cloud Sync)
1. Go to Firebase Console → Project Settings → Service Accounts.
2. Click **Generate new private key**.
3. Save the downloaded JSON file as `firebase-service-account.json` in the **root folder** of this project. (This file is `.gitignore`d automatically).
4. Update `FIREBASE_DB_URL` inside `recognition/firebase_sync.py` to your Realtime Database URL.

### For the Web Dashboard
1. Go to Firebase Console → Project Settings → General, and find your "Web App" configuration keys.
2. Open `dashboard/firebase-config.js` and replace the placeholder keys with your actual config.
3. In Firebase Console, go to Authentication, enable **Email/Password**, and create a single admin account (e.g., `admin@test.com`).

---

## 3. Running the System

### Step A: Register Students
Run the enrollment script. It will ask for student details, capture 5 face angles to create a robust embedding, and generate a printable QR code PNG.
```bash
python recognition/register_student.py
```

### Step B: Start the Recognition Pipeline
Start the main webcam loop. The background thread will automatically start syncing to Firebase if connected.
```bash
python recognition/main.py
```
Hold up the generated QR code and your face to the camera to log attendance.

### Step C: Open the Dashboard
You don't need a build system to view the dashboard! Simply open `dashboard/index.html` in any modern web browser, or serve it using Python:
```bash
cd dashboard
python -m http.server 8000
# Then visit http://localhost:8000 in your browser
```
Log in using the admin account you created in Firebase Auth.
