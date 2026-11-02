# PPE Sentinel — Teammate Demo & Presentation Quickstart

This guide is for **Sandesh Vairagar** and **Prathamesh Shelke** to run the hardware demo independently on their laptops without needing Vedant's laptop.

---

## 🚀 Step 1: Initial Laptop Setup (One-Time Only)
If your laptop doesn't have the Python libraries installed yet:
1. Make sure **Python 3.10 or 3.11** is installed on your laptop (from python.org, with *"Add Python to PATH"* checked).
2. Double-click **`SETUP_NEW_LAPTOP.bat`**.
   - This automatically installs FastAPI, OpenCV, YOLOv8, PySerial, etc.

---

## 🔌 Step 2: Plug in the Hardware
1. Plug the **Arduino Uno USB cable** into your laptop.
   - *Note: You do not need to worry about the COM port! The system automatically scans COM1 through COM10 and auto-connects to the Arduino.*
2. Ensure your laptop's **webcam** is active.

---

## ⚡ Step 3: Start the System (Demo Day)
1. Double-click **`START_WEBSITE.bat`**.
   - A command window will open.
   - It will automatically connect to your Arduino, load the YOLOv8 AI model (`best.pt`), and start the SCADA web server.
2. Open your web browser (Chrome or Edge) at:
   ### **http://127.0.0.1:8000**

---

## 🎯 Step 4: Demo Walkthrough for Examiners

### A. Automatic Compliant Entry Demo:
1. Have someone stand in front of the camera wearing **both Hardhat and Safety Vest**.
2. Bring a hand/object within **100 cm** of the HC-SR04 ultrasonic sensor (or walk up to the gate).
3. **What happens:**
   - The HUD highlights both Hardhat & Vest with green bounding boxes.
   - The streak meter counts 2 consecutive frames.
   - Green LED turns ON.
   - The SG90 servo motor smoothly sweeps (1.10s) from **0° to 90°**.
   - The barrier stays open for **15.0 seconds** for safe entry clearance, then automatically sweeps closed.

### B. Automatic Violation & Cloud Alert Demo:
1. Remove either the hardhat or the vest.
2. Approach within **100 cm**.
3. **What happens:**
   - Red LED flashes and buzzer sounds.
   - Barrier remains strictly locked at **0°**.
   - High-resolution violation snapshot is automatically captured and logged.
   - An instant incident alert photo is dispatched to the Telegram Bot (`@Construction_Safety_Alerts_Bot`).

### C. Manual Control & Diagnostics (Right Panel):
- **`OPEN (15s)`**: Manually trigger 15-second entry sweep.
- **`CLOSE GATE`**: Manually lock barrier to 0°.
- **`TELEGRAM TEST`**: Dispatch a live test notification to Telegram to prove cloud integration.
- **`3D HARDWARE SCHEMATIC`**: Click to show the interactive 3D component wiring layout to the examiner.

---

*Project developed by Vedant Patke, Sandesh Vairagar, and Prathamesh Shelke.*

