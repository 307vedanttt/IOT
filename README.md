# 🛡️ Sentinel — Smart Autonomous Industrial Safety Gate (PPE Compliance SCADA)

> An Edge AI and IoT-powered physical security gate that enforces 100% compliance with Personal Protective Equipment (Hardhat + Safety Vest) before authorizing entry. Features real-time computer vision inference, microsecond servo sweep trajectories, live ultrasonic sonar, and automated cloud incident alerts via Telegram.

---

## 👥 Core Engineering Team

| Engineer | Role & Headline | Profile |
| :--- | :--- | :--- |
| **Vedant Patke** | Computer Science & AI Engineering Student | [LinkedIn Profile](https://www.linkedin.com/in/vedant-patke-0761a232a/) |
| **Sandesh Vairagar** | Computer Science & Engineering (AI) Student | [LinkedIn Profile](https://www.linkedin.com/in/sandesh-vairagar) |
| **Prathamesh Shelke** | Software Engineer & Full-Stack Developer | [LinkedIn Profile](https://in.linkedin.com/in/prathamesh-shelke-86829b32a) |

---

## ⚙️ Architecture & Hardware Assembly

- **Microcontroller:** Arduino Uno (ATmega328P) via USB Serial (`9600` baud)
- **Actuator:** SG90 Micro Servo (Pin 6) with deterministic 1.10s smooth trajectory sweep (0°–90°) and 15.0s entry clearance hold
- **Proximity Sensor:** HC-SR04 Ultrasonic Distance Sensor (Pins 4 & 5, trigger threshold `< 100 cm`)
- **Visual Beacons:** Green Access LED (Pin 8), Red Violation LED (Pin 9)
- **Acoustic Alarm:** Active Piezo Buzzer (Pin 10, 2.4 kHz alert warble)
- **Local Telemetry Twin:** HD44780 16x2 Character LCD via PCF8574 I2C Backpack (Pins A4/A5)
- **Edge AI Vision:** Ultralytics YOLOv8 custom-trained weights (`best.pt`) detecting Hardhat (Class 0), Safety Vest (Class 7), and Person (Class 5)
- **Cloud Automation:** Two-way Telegram Bot API integration (`@Construction_Safety_Alerts_Bot`) with 40-second alert cooldown rate-limiting

---

## 🚀 Quickstart Guide (Running on Any Team Laptop)

### 1. Prerequisites
- Python 3.10 or 3.11 installed (ensure **"Add Python to PATH"** is checked during Python setup).

### 2. One-Time Dependency Setup
Double-click:
```cmd
SETUP_NEW_LAPTOP.bat
```
*(Installs FastAPI, Uvicorn, OpenCV, Ultralytics YOLOv8, PySerial, etc.)*

### 3. Start the Platform
1. Plug the **Arduino Uno USB cable** into your laptop.
2. Double-click:
```cmd
START_WEBSITE.bat
```
3. Open your browser at:
### **http://127.0.0.1:8000**

---

## 📁 Repository Structure

```text
├── app.py                      # FastAPI backend SCADA ASGI application
├── best.pt                     # YOLOv8 custom trained PPE weights (23.4 MB)
├── arduino_gate_sketch/        # Arduino C++ firmware for ATmega328P
├── static/                     # Digital twin backdrops, 3D renders & developer assets
├── templates/                  # SCADA HUD, Reports, Audit Trail & Settings templates
├── telegram_automation.py      # Asynchronous Telegram bot alert engine
├── requirements.txt            # Python dependencies
├── START_WEBSITE.bat           # 1-click universal launcher for team laptops
├── SETUP_NEW_LAPTOP.bat        # 1-click dependency installer
└── TEAM_DEMO_GUIDE.md          # Examiner presentation & demo cheat sheet
```

---

## 📜 License & Acknowledgments
Academic Capstone Engineering Project developed by **Vedant Patke, Sandesh Vairagar, and Prathamesh Shelke**.
