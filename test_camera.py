import cv2

CAMERA_INDEX = 0  # try 1 if you get a black or missing image

print(f"Attempting to open camera at index {CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print(f"Cannot open camera index {CAMERA_INDEX}.")
    print("Trying index 1...")
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        raise SystemExit("Cannot open any camera. Close Zoom, Teams or browser tabs using webcam.")

print("Camera feed active! Press 'q' in the camera window to exit.")

while True:
    ok, frame = cap.read()
    if not ok:
        print("Failed to grab frame.")
        break

    cv2.imshow("Camera test (press q to quit)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("Camera test completed successfully.")

