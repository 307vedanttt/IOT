# Smart Lab Attendance System — Testing Checklist

Before the final viva/demo, run through these test scenarios to confirm everything works end-to-end.

## 1. Recognition Pipeline & Logic

- [ ] **Valid Entry**: Show a valid registered QR card + the matching face.
  - *Expected*: Terminal prints `[ENTRY] student_id=XYZ`, UI shows Green `MATCH: ENTRY`.
  - *Dashboard*: Event appears in "Recent Events", student appears in "Currently Inside Lab".
- [ ] **Valid Exit (Toggle Logic)**: Show the same valid card + matching face again.
  - *Expected*: Terminal prints `[EXIT] student_id=XYZ`, UI shows Green `MATCH: EXIT`.
  - *Dashboard*: Event appears in "Recent Events", student is **removed** from "Currently Inside Lab".
- [ ] **Proxy Attempt (Card + Wrong Face)**: Show a valid QR card, but a different person's face.
  - *Expected*: After 2 consecutive failed match attempts, terminal prints `[PROXY ATTEMPT] card=XYZ reason=face_mismatch`, UI shows Red `MISMATCH (Proxy?)`.
  - *Dashboard*: Attempt is logged in the "Proxy / Mismatch Log" panel.
- [ ] **Card Timeout (Card + No Face)**: Hold up a valid QR card but cover/hide your face entirely for ~5 seconds.
  - *Expected*: UI initially shows Yellow `Waiting for 2nd factor...`. After timeout, terminal prints `[PROXY ATTEMPT] card=XYZ reason=no_face`, UI shows Orange `CARD BUT NO FACE`.
  - *Dashboard*: Appears in the "Proxy / Mismatch Log".
- [ ] **Ignored Face (Face + No Card)**: Stand in front of the camera with no QR card visible.
  - *Expected*: The system ignores the face. No events are logged (prevents cluttering the database when people just walk past).
- [ ] **Debounce Window**: Immediately after a successful MATCH, show the same card + face again within 30 seconds.
  - *Expected*: UI shows Cyan `ALREADY LOGGED`. Event is not recorded (prevents duplicate logs).

## 2. Sync & Offline Capabilities

- [ ] **Offline Buffering**: Disconnect your Wi-Fi, then perform a successful MATCH.
  - *Expected*: Terminal prints `[OFFLINE] Buffering locally... (No internet connection)`. The event is saved to SQLite with `synced=0`.
- [ ] **Automatic Re-sync**: Reconnect your Wi-Fi and wait for up to 15 seconds.
  - *Expected*: Terminal prints `[SYNCED] Pushed X events to Firebase`.
  - *Dashboard*: The buffered event suddenly appears on the live dashboard. No duplicates are created.

## 3. Web Dashboard

- [ ] **Authentication**: Open `dashboard/index.html` in an incognito window.
  - *Expected*: You must see the Login screen. You cannot view data without logging in.
- [ ] **Search & Filter**: Type a name or ID into the search bar.
  - *Expected*: The "Recent Events" feed immediately filters to only show matching rows.
- [ ] **CSV Export**: Click the "Export CSV" button.
  - *Expected*: A `.csv` file downloads automatically, containing exactly the rows currently visible in the feed (respecting your search filter).
- [ ] **Safety Banner**: Manually push dummy data to Firebase Realtime Database at `safety_readings/lab_1` (e.g., set `alert_status` to `"ALERT"`).
  - *Expected*: The dashboard banner instantly turns Red and says `ALERT TRIGGERED! (ALERT)`.
