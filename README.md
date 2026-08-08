# Smart Lab Attendance System

A camera-based lab attendance system that identifies students using TWO factors simultaneously:
1. QR Code (on student ID card)
2. Face Recognition

Attendance is logged only if the face matches the registered student ID in the QR code.

## Tech Stack
- **Python 3**: Recognition pipeline
- **OpenCV & face_recognition**: Face detection and encoding
- **cv2.QRCodeDetector / pyzbar**: QR code decoding
- **SQLite**: Offline local buffering
- **Firebase Realtime Database**: Cloud sync
- **HTML/CSS/JS**: Web dashboard

## Project Structure
- `recognition/`: The Python camera pipeline and data sync logic.
- `dashboard/`: The web dashboard for viewing attendance and sensor data.
- `data/`: Local storage for faces, encodings, and the SQLite database.

## Setup Instructions

### 1. Environment Setup
Create and activate a Python virtual environment:
```bash
cd recognition
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### Troubleshooting Dependencies
- **dlib / face_recognition**: You need CMake and a C++ compiler installed on your system. 
  - On Windows: Install Visual Studio Build Tools (C++ development workload).
  - On Linux: `sudo apt install cmake build-essential`
  - On Mac: `brew install cmake`
- **pyzbar**: Requires the zbar shared library.
  - On Windows: Download ZBar DLL from sourceforge.
  - On Linux: `sudo apt install libzbar0`
  - On Mac: `brew install zbar`

### 3. Firebase Setup
1. Create a Firebase project and enable Realtime Database.
2. Go to Project Settings > Service Accounts and generate a new private key.
3. Save the JSON file as `recognition/serviceAccountKey.json`.
4. Update `FIREBASE_DB_URL` in `recognition/firebase_sync.py`.
5. Get your Firebase JS config and update `dashboard/firebase-config.js`.

### 4. Running the System

**Step A: Register Students**
Run the registration script to enroll a student (captures face + saves details):
```bash
python register_student.py
```
*(This will also generate a sample QR code image for testing).*

**Step B: Start the Recognition Pipeline**
Run the main webcam loop:
```bash
python main.py
```
Hold up a registered QR code and your face to the camera to log attendance.

**Step C: View Dashboard**
Open `dashboard/index.html` in your browser. (You can use a simple static server like `python -m http.server 8000` inside the `dashboard/` directory if needed for module loading, though plain file:// might work for simple setups).
