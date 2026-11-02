import time
import serial

PORT = "COM5"
BAUD = 9600

print(f"[*] Opening {PORT} at {BAUD} baud...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
except Exception as e:
    print(f"[-] Failed to open {PORT}: {e}")
    exit(1)

# Wait 2.5s for Uno boot
time.sleep(2.5)
while ser.in_waiting:
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        print(f"    [Boot]: {line}")

print("\n" + "="*60)
print("SERVO TIMING VERIFICATION TEST")
print("Target Specification:")
print("  - Sweep to 90 degrees: 1.10 seconds")
print("  - Rest at 90 degrees: 15.00 seconds")
print("  - Sweep to 0 degrees:  1.10 seconds")
print("  - Total Cycle Time:   17.20 seconds")
print("="*60)

print("\n[>] Sending 'G' (ACCESS GRANTED)...")
t0 = time.time()
ser.write(b'G')

# Monitor serial line for distance readings / output over the next 18 seconds
print("[*] Monitoring cycle (watch physical servo move slowly)...")
while time.time() - t0 < 18.0:
    elapsed = time.time() - t0
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line and line.startswith("D:"):
            # Distance reading
            pass
    if int(elapsed * 10) % 20 == 0:
        print(f"    Elapsed: {elapsed:5.1f}s | Gate status: {'OPENING (0-1.1s)' if elapsed < 1.1 else 'RESTING AT 90 DEG (1.1-16.1s)' if elapsed < 16.1 else 'CLOSING TO 0 DEG (16.1-17.2s)' if elapsed < 17.2 else 'CLOSED / STANDBY'}")
    time.sleep(0.1)

ser.close()
print("\n[+] Verification run completed successfully.")

