import time
import serial

# Arduino COM port detected on your machine
SERIAL_PORT = "COM5"

print(f"Connecting to Arduino on {SERIAL_PORT} at 9600 baud...")

try:
    ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
except Exception as e:
    raise SystemExit(
        f"Could not open {SERIAL_PORT}: {e}\n"
        "Make sure:\n"
        "1. The Arduino is plugged into USB.\n"
        "2. The Arduino Serial Monitor in Arduino IDE is CLOSED (only one app can use COM port at a time).\n"
        "3. Check Device Manager or Arduino IDE Tools -> Port to verify the correct COM port."
    )

time.sleep(2)  # Arduino resets when serial port opens

commands = [
    ("C", "checking"),
    ("G", "granted"),
    ("H", "helmet missing"),
    ("V", "vest missing"),
    ("R", "both missing"),
    ("I", "idle"),
]

print("Starting command sequence...")
for cmd, label in commands:
    print(f"Sending '{cmd}' -> {label}")
    ser.write(cmd.encode())
    time.sleep(3)

ser.close()
print("All commands sent successfully.")

