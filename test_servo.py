import time
import serial

PORT = "COM5"
BAUD = 9600

print(f"[*] Opening {PORT} at {BAUD} baud...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
except Exception as e:
    print(f"[-] Failed to open {PORT}: {e}")
    print("[!] Ensure Arduino IDE Serial Monitor is CLOSED.")
    exit(1)

# Arduino reboots on serial connection; wait 2.5s for initialization
time.sleep(2.5)

# Read any startup telemetry
while ser.in_waiting:
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        print(f"    [Arduino boot]: {line}")

print("\n" + "="*60)
print("--- TEST: ACCESS GRANTED ('G') FULL 15-SECOND CYCLE ---")
print("Target: Servo sweeps 0 -> 90 deg (1.10s), holds for 15.0s, sweeps 90 -> 0 deg (1.10s)")
print("Total Expected Duration: 17.20 seconds")
print("="*60)

print("\n[>] Sending 'G' (ACCESS GRANTED)...")
t0 = time.time()
ser.write(b'G')

while time.time() - t0 < 19.0:
    elapsed = time.time() - t0
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line and line.startswith("D:"):
            # Distance telemetry
            pass
    if int(elapsed * 10) % 20 == 0:
        if elapsed < 1.1:
            phase = "OPENING (0 -> 90 deg, ~1.1s)"
        elif elapsed < 16.1:
            phase = f"RESTING AT 90 DEG ({15.0 - (elapsed - 1.1):4.1f}s remaining)"
        elif elapsed < 17.5:
            phase = "CLOSING (90 -> 0 deg, ~1.1s)"
        else:
            phase = "FULLY CLOSED AT 0 DEG (STANDBY)"
        print(f"    [T+{elapsed:4.1f}s] {phase}")
    time.sleep(0.1)

ser.close()
print("\n[+] Test complete. Serial port closed.")
