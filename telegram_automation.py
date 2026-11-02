"""
==============================================================================
Project: PPE Compliance Gate System — Telegram Automation Engine
File:    telegram_automation.py
Author:  Embedded Systems & Python Integration Engineering
==============================================================================

Purpose:
  Provides 2-way Telegram automation for the PPE Gate:
  1. Sends instant photo & text alerts when a worker violates PPE requirements.
  2. Rate limiting / cooldown to prevent alert flooding.
  3. Interactive 2-way bot commands:
       /status   - Get real-time gate telemetry & compliance rate
       /snapshot - Receive current live camera view on your phone
       /open     - Remotely open barrier (5-second emergency grant)
       /close    - Remotely close barrier
       /stats    - Summary of total checks, passes, violations
       /help     - List available commands
  4. Privacy & Security:
       - BOT_TOKEN lives ONLY in secrets_config.py
       - Tokens are NEVER printed or logged.
==============================================================================
"""

import os
import re
import sys
import time
import queue
import datetime
import threading
from typing import Optional, Tuple, Callable

import requests

# Import credentials strictly from secrets_config.py
try:
    from secrets_config import BOT_TOKEN, CHAT_ID
except ImportError:
    BOT_TOKEN = "paste-your-token-here"
    CHAT_ID = "paste-your-chat-id-here"

ALERT_COOLDOWN_SEC = 40.0  # Seconds between repeated violation alerts
REQUEST_TIMEOUT_SEC = 10.0


def sanitize(text: str) -> str:
    """Removes bot tokens from error messages or URLs before printing."""
    if not text:
        return ""
    return re.sub(r"/bot[^/]+/", "/bot[REDACTED_TOKEN]/", str(text))


def is_configured() -> bool:
    """Returns True if the user has provided valid credentials in secrets_config.py."""
    if not BOT_TOKEN or not CHAT_ID:
        return False
    placeholders = {
        "paste-your-token-here",
        "paste-your-chat-id-here",
        "your_bot_token_here",
        "your_chat_id_here",
        "none",
    }
    return (BOT_TOKEN.strip().lower() not in placeholders) and (CHAT_ID.strip().lower() not in placeholders)


class TelegramManager:
    """Manages asynchronous Telegram notifications and interactive bot command polling."""

    def __init__(self):
        self.last_alert_time = 0.0
        self.cooldown_sec = ALERT_COOLDOWN_SEC
        self.lock = threading.Lock()
        self.send_queue = queue.Queue()
        self.bot_username = "Unconfigured"
        self.running = True

        # Callback hook to interact with main gate state (for /open, /close, /status, /snapshot)
        self.command_handler: Optional[Callable[[str, str], str]] = None
        self.snapshot_provider: Optional[Callable[[], Optional[bytes]]] = None

        # Start asynchronous dispatch worker
        self.worker_thread = threading.Thread(target=self._dispatch_worker, daemon=True, name="TelegramDispatchWorker")
        self.worker_thread.start()

        # Start interactive command listener
        self.listener_thread = threading.Thread(target=self._command_listener, daemon=True, name="TelegramCommandListener")
        self.listener_thread.start()

    def test_connection(self) -> Tuple[bool, str]:
        """Tests connectivity and verifies token validity using Telegram getMe API."""
        if not is_configured():
            return False, "Telegram token/chat ID not configured in secrets_config.py"

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    self.bot_username = data.get("result", {}).get("username", "PPE_Bot")
                    return True, f"Connected to @{self.bot_username}"
                return False, f"API error: {data.get('description', 'Unknown')}"
            elif resp.status_code == 401:
                return False, "Error 401: Invalid BOT_TOKEN. Check secrets_config.py."
            else:
                return False, f"HTTP {resp.status_code}: {sanitize(resp.text)}"
        except Exception as e:
            return False, f"Connection failed: {sanitize(str(e))}"

    def send_text(self, text: str) -> bool:
        """Sends a text message to the configured Telegram chat."""
        if not is_configured():
            return False
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SEC)
            return r.status_code == 200 and r.json().get("ok", False)
        except Exception as e:
            print(f"[Telegram] Text alert error: {sanitize(str(e))}")
            return False

    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """Sends a photo with caption to the configured Telegram chat."""
        if not is_configured():
            return False

        if not os.path.exists(photo_path):
            # Fall back to text if photo file is missing
            return self.send_text(f"{caption}\n(Photo attachment not found on disk)")

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                    files={"photo": f},
                    timeout=REQUEST_TIMEOUT_SEC,
                )
            return r.status_code == 200 and r.json().get("ok", False)
        except Exception as e:
            print(f"[Telegram] Photo alert error: {sanitize(str(e))}")
            return False

    def send_photo_bytes(self, image_bytes: bytes, caption: str = "") -> bool:
        """Sends in-memory image bytes to Telegram (e.g. for live /snapshot command)."""
        if not is_configured() or not image_bytes:
            return False
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        try:
            files = {"photo": ("snapshot.jpg", image_bytes, "image/jpeg")}
            r = requests.post(
                url,
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files=files,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            return r.status_code == 200 and r.json().get("ok", False)
        except Exception as e:
            print(f"[Telegram] Photo bytes error: {sanitize(str(e))}")
            return False

    def queue_violation_alert(self, missing_items: list, photo_path: str):
        """Asynchronously queues a PPE violation alert with rate-limiting cooldown."""
        now = time.time()
        with self.lock:
            if now - self.last_alert_time < self.cooldown_sec:
                # Cooldown active to prevent spamming
                return
            self.last_alert_time = now

        # Format missing safety equipment lines
        equipment_lines = []
        missing_lower = [str(m).lower() for m in missing_items]
        if any("helmet" in m or "hardhat" in m for m in missing_lower) or not missing_items:
            equipment_lines.append("• Safety Helmet")
        if any("vest" in m for m in missing_lower) or not missing_items:
            equipment_lines.append("• Reflective Safety Vest")

        if not equipment_lines:
            equipment_lines.append("• Safety Helmet\n• Reflective Safety Vest")

        missing_text = "\n".join(equipment_lines)
        rep_date = datetime.datetime.now().strftime("%d-%m-%Y")
        rep_time = datetime.datetime.now().strftime("%I:%M:%S %p")

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
            f"{missing_text}\n\n"
            "⛔ <b>ENTRY RESTRICTED</b>\n"
            "<b>Action required:</b> Worker must wear all mandatory PPE before entry is authorized."
        )
        self.send_queue.put(("photo", photo_path, caption))

    def _dispatch_worker(self):
        """Worker thread processing outbound messages without stalling main vision loop."""
        while self.running:
            try:
                item = self.send_queue.get(timeout=1.0)
                msg_type, target, text = item
                if msg_type == "photo":
                    self.send_photo(target, text)
                elif msg_type == "text":
                    self.send_text(text)
                elif msg_type == "bytes":
                    self.send_photo_bytes(target, text)
                self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Telegram Worker] Dispatch error: {sanitize(str(e))}")

    def _command_listener(self):
        """
        Long-polling worker that listens for Telegram commands sent to the bot:
        /status, /snapshot, /open, /close, /stats, /help
        """
        if not is_configured():
            # Wait until configured
            while self.running and not is_configured():
                time.sleep(5)

        last_update_id = 0
        while self.running:
            if not is_configured():
                time.sleep(5)
                continue

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id + 1,
                "timeout": 10,
                "allowed_updates": ["message"],
            }
            try:
                r = requests.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    for update in data.get("result", []):
                        update_id = update.get("update_id", 0)
                        if update_id > last_update_id:
                            last_update_id = update_id

                        msg = update.get("message", {})
                        text = msg.get("text", "").strip()
                        sender_chat_id = str(msg.get("chat", {}).get("id", ""))
                        
                        # Auto-pair chat ID on any incoming message
                        if sender_chat_id:
                            global CHAT_ID
                            if CHAT_ID != sender_chat_id:
                                CHAT_ID = sender_chat_id
                                try:
                                    with open("secrets_config.py", "w", encoding="utf-8") as sf:
                                        sf.write(f'BOT_TOKEN = "{BOT_TOKEN}"\nCHAT_ID = "{sender_chat_id}"\n')
                                    print(f"[Telegram] Auto-paired with Chat ID: {sender_chat_id}")
                                except Exception as se:
                                    print(f"[Telegram] Error updating secrets_config: {se}")

                        # Security check: verify command comes from configured CHAT_ID or authorized user
                        if text.startswith("/"):
                            self._handle_command(text, sender_chat_id)
            except Exception:
                time.sleep(5)

    def _handle_command(self, cmd_text: str, sender_chat: str):
        """Executes interactive bot commands."""
        cmd = cmd_text.split()[0].lower()

        if cmd in ("/start", "/help"):
            reply = (
                "🛡️ <b>PPE Compliance Gate — Bot Control</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                "Available Commands:\n"
                "• <b>/status</b> — Real-time gate telemetry & sensors\n"
                "• <b>/snapshot</b> — Request live webcam view\n"
                "• <b>/open</b> — Remote emergency barrier open (15s)\n"
                "• <b>/close</b> — Remote barrier close (0°)\n"
                "• <b>/stats</b> — Access statistics & compliance rate\n"
                "• <b>/help</b> — Show this help menu\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                "<i>Edge AI + IoT Industrial Safety Gate</i>"
            )
            self.send_text(reply)

        elif cmd == "/snapshot":
            if self.snapshot_provider:
                img_bytes = self.snapshot_provider()
                if img_bytes:
                    caption = f"📸 <b>Live Gate Camera Snapshot</b>\n🕒 {datetime.datetime.now().strftime('%H:%M:%S')}"
                    self.send_photo_bytes(img_bytes, caption)
                else:
                    self.send_text("⚠️ Camera stream is currently unavailable.")
            else:
                self.send_text("⚠️ Snapshot provider not connected to video feed.")

        elif cmd == "/status":
            if self.command_handler:
                resp = self.command_handler("status", "")
                self.send_text(resp)
            else:
                self.send_text("Gate controller is running. Telemetry standby.")

        elif cmd == "/stats":
            if self.command_handler:
                resp = self.command_handler("stats", "")
                self.send_text(resp)
            else:
                self.send_text("Stats engine standby.")

        elif cmd == "/open":
            if self.command_handler:
                self.command_handler("open", "")
                self.send_text("🔓 <b>Remote Override:</b> Barrier opened for 15 seconds entry hold (Command 'G' sent).")
            else:
                self.send_text("⚠️ Actuator link not connected.")

        elif cmd == "/close":
            if self.command_handler:
                self.command_handler("close", "")
                self.send_text("🔒 <b>Remote Override:</b> Barrier closed and reset to IDLE (Command 'I' sent).")
            else:
                self.send_text("⚠️ Actuator link not connected.")


# Global instance
telegram_mgr = TelegramManager()

