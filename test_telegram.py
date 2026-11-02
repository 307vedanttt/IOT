import os
import requests

try:
    from secrets_config import BOT_TOKEN, CHAT_ID
except ImportError:
    raise SystemExit("secrets_config.py not found. Please create it first.")

if not BOT_TOKEN or BOT_TOKEN == "paste-your-token-here" or not CHAT_ID or CHAT_ID == "paste-your-chat-id-here":
    print("Please edit secrets_config.py and put your real BOT_TOKEN and CHAT_ID first.")
    exit(1)

sample_file = "sample.jpg"
if not os.path.exists(sample_file):
    import cv2
    import numpy as np
    blank = np.zeros((300, 400, 3), dtype=np.uint8)
    cv2.putText(blank, "PPE Gate Test Alert", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imwrite(sample_file, blank)

from datetime import datetime

rep_date = datetime.now().strftime("%d-%m-%Y")
rep_time = datetime.now().strftime("%I:%M:%S %p")

caption = (
    "👷 <b>Construction Safety Bot</b>\n"
    "<i>Automated safety alert — Violation</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <b>PPE VIOLATION DETECTED</b>\n"
    "<b>Worker Safety Report</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    f"📅 <b>Reporting date:</b> {rep_date}\n"
    f"⏰ <b>Reporting time:</b> {rep_time}\n"
    "📍 <b>Location:</b> Main Entry Gate\n"
    "👤 <b>Worker ID:</b> Not identified\n\n"
    "🚫 <b>Missing safety equipment:</b>\n"
    "• Safety Helmet\n"
    "• Reflective Safety Vest\n\n"
    "⛔ <b>ENTRY RESTRICTED</b>\n"
    "<b>Action required:</b> Worker must wear all mandatory PPE before entry is authorized."
)

print("Sending test photo alert to Telegram...")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

try:
    with open(sample_file, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=10,
        )
    print(f"HTTP Status: {r.status_code}")
    if r.status_code == 200:
        print("Success! Photo received on Telegram.")
    else:
        print(f"Telegram response: {r.text}")
        if r.status_code == 401:
            print("Error 401: Invalid BOT_TOKEN.")
        elif "chat not found" in r.text.lower():
            print("Chat not found: Make sure you pressed Start in your bot chat or check CHAT_ID.")
except Exception as e:
    print("Telegram request error:", e)

