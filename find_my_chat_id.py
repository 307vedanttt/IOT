"""
Helper Tool: Auto-Detect Telegram Chat ID
=========================================
If you created a bot with @BotFather and pasted your BOT_TOKEN into secrets_config.py:
1. Open your bot on Telegram and send any message (like 'hi' or press Start).
2. Run this script: python find_my_chat_id.py
3. It will automatically detect your Chat ID and save it into secrets_config.py!
"""

import sys
import re
import requests

try:
    from secrets_config import BOT_TOKEN, CHAT_ID
except ImportError:
    print("[-] secrets_config.py not found.")
    sys.exit(1)

if not BOT_TOKEN or BOT_TOKEN.strip().lower() in ("paste-your-token-here", "none", ""):
    print("=" * 60)
    print("STEP 1: You need your BOT_TOKEN first!")
    print("=" * 60)
    print("1. Open Telegram and search for: @BotFather")
    print("2. Send: /newbot")
    print("3. Follow instructions to name your bot.")
    print("4. BotFather will reply with your HTTP API Token (e.g. 7123456789:ABC...).")
    print("5. Open secrets_config.py and paste it as BOT_TOKEN = '...'")
    print("6. Then run this script again!")
    sys.exit(0)

print(f"[*] Checking updates for bot token...")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

try:
    resp = requests.get(url, timeout=10)
    if resp.status_code == 401:
        print("[-] Error 401: Invalid BOT_TOKEN in secrets_config.py. Check the token from @BotFather.")
        sys.exit(1)
    
    data = resp.json()
    updates = data.get("result", [])
    
    if not updates:
        # Check bot name
        me_resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10).json()
        bot_name = me_resp.get("result", {}).get("username", "your bot")
        print("\n" + "=" * 60)
        print(f"[!] No messages received yet by @{bot_name}!")
        print("=" * 60)
        print(f"1. Open Telegram on your phone.")
        print(f"2. Search for your bot: @{bot_name}")
        print(f"3. Tap 'START' (or send 'hello').")
        print(f"4. Run this script again: python find_my_chat_id.py\n")
        sys.exit(0)
    
    # Get latest message sender
    latest = updates[-1]
    msg = latest.get("message") or latest.get("channel_post") or {}
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    first_name = chat.get("first_name", "User")
    username = chat.get("username", "")

    if chat_id:
        print("\n" + "=" * 60)
        print(f"[+] FOUND YOUR TELEGRAM CHAT ID!")
        print(f"    Name:    {first_name} (@{username})")
        print(f"    Chat ID: {chat_id}")
        print("=" * 60)

        # Update secrets_config.py automatically
        with open("secrets_config.py", "r", encoding="utf-8") as f:
            content = f.read()

        new_content = re.sub(r'CHAT_ID\s*=\s*["\'].*?["\']', f'CHAT_ID = "{chat_id}"', content)
        with open("secrets_config.py", "w", encoding="utf-8") as f:
            f.write(new_content)

        print("[+] Automatically updated secrets_config.py with your Chat ID!")
        print("[+] Now sending a test confirmation message to your phone...")

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(send_url, json={
            "chat_id": chat_id,
            "text": "🎉 <b>PPE Gate System Connected!</b>\nYour Telegram account is now linked to receive live PPE violation alerts.",
            "parse_mode": "HTML"
        }, timeout=10)
        print("[+] Confirmation sent! Check your Telegram app.")
    else:
        print("[-] Could not find chat ID in updates. Send a message to your bot first.")

except Exception as e:
    print(f"[-] Error: {e}")

