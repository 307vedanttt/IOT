"""
simulate_hardware.py — Tinkercad Hardware Simulator
===================================================
Run this script during your demo to simulate the Tinkercad circuit sending 
safety sensor data (Temperature, Gas, Humidity) to the Firebase database.
It will automatically trigger the Safety Banner on the dashboard!
"""

import time
import random
import firebase_admin
from firebase_admin import credentials, db

# Setup
FIREBASE_DB_URL = "https://smart-lab-attendance-default-rtdb.firebaseio.com/" # Replace with yours
SERVICE_ACCOUNT_PATH = "recognition/firebase-service-account.json"

print("Initializing Firebase for Hardware Simulation...")
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})

safety_ref = db.reference('safety_readings/lab_1')

print("Hardware Simulation Running. Pushing data every 5 seconds...")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        # Simulate normal readings most of the time, occasionally spike to cause an alert
        is_alert = random.choice([False, False, False, False, True]) # 20% chance of alert
        
        temp = round(random.uniform(22.0, 25.0), 1) if not is_alert else round(random.uniform(40.0, 60.0), 1)
        gas = round(random.uniform(10.0, 30.0), 1) if not is_alert else round(random.uniform(150.0, 300.0), 1)
        humidity = round(random.uniform(40.0, 50.0), 1)
        
        status = "ALERT" if is_alert else "NORMAL"
        
        reading = {
            "temperature": temp,
            "gas_level": gas,
            "humidity": humidity,
            "alert_status": status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        
        safety_ref.set(reading)
        
        if is_alert:
            print(f"🔥 [DANGER] Pushed ALERT state: Temp={temp}°C, Gas={gas}ppm")
        else:
            print(f"✅ [NORMAL] Pushed reading: Temp={temp}°C, Gas={gas}ppm")
            
        time.sleep(5)

except KeyboardInterrupt:
    print("\nHardware simulation stopped.")
