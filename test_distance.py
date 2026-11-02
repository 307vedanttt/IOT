import serial

# Arduino COM port detected on your machine
SERIAL_PORT = "COM5"

print(f"Connecting to Arduino on {SERIAL_PORT}...")

try:
    ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
except Exception as e:
    raise SystemExit(
        f"Could not open {SERIAL_PORT}: {e}\n"
        "Ensure Arduino is plugged in and Arduino IDE Serial Monitor is closed."
    )

print("Reading ultrasonic distance sensor. Move your hand in front of the sensor.")
print("Press Ctrl+C in terminal to stop.\n")

try:
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line.startswith("D:"):
            cm_val = line[2:]
            print(f"Distance: {cm_val} cm")
except KeyboardInterrupt:
    print("\nStopping sensor reading test.")
finally:
    ser.close()

