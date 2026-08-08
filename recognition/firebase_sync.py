"""
firebase_sync.py — Offline Buffering & Firebase Realtime Database Sync
=======================================================================
"""

import threading
import time
import socket
import firebase_admin
from firebase_admin import credentials, db as rtdb
import local_db
import os

FIREBASE_DB_URL = "https://smart-lab-attendance-default-rtdb.firebaseio.com/" # Replace later
SERVICE_ACCOUNT_PATH = "./firebase-service-account.json"
SYNC_INTERVAL = 15 # seconds

_firebase_initialized = False
_sync_thread_running = False

def init_firebase() -> bool:
    global _firebase_initialized
    if _firebase_initialized:
        return True
        
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        # We can't initialize without credentials
        return False
        
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        _firebase_initialized = True
        return True
    except Exception as e:
        print(f"Firebase init error: {e}")
        return False

def check_connectivity(host="8.8.8.8", port=53, timeout=3) -> bool:
    """Simple check to determine if internet is reachable."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False

def sync_pending_events():
    """Background thread function to push unsynced events to Firebase."""
    global _sync_thread_running
    _sync_thread_running = True
    
    while _sync_thread_running:
        if not init_firebase():
            print("[OFFLINE] Buffering locally... (Missing firebase credentials or init failed)")
            time.sleep(SYNC_INTERVAL)
            continue
            
        if not check_connectivity():
            print("[OFFLINE] Buffering locally... (No internet connection)")
            time.sleep(SYNC_INTERVAL)
            continue
            
        unsynced = local_db.get_unsynced_events()
        if not unsynced:
            time.sleep(SYNC_INTERVAL)
            continue
            
        success_count = 0
        for event in unsynced:
            table = event.pop('table')
            try:
                if table == 'attendance_events':
                    event_id = event.pop('event_id')
                    ref = rtdb.reference(f'attendance_events/{event_id}')
                    ref.set(event) # Safe: sets the data at this specific path (idempotent)
                    local_db.mark_as_synced(table, event_id)
                    success_count += 1
                elif table == 'mismatch_logs':
                    log_id = event.pop('log_id')
                    ref = rtdb.reference(f'mismatch_logs/{log_id}')
                    ref.set(event)
                    local_db.mark_as_synced(table, log_id)
                    success_count += 1
            except Exception as e:
                print(f"[SYNC ERROR] Failed to push {table} row: {e}")
                
        if success_count > 0:
            print(f"[SYNCED] Pushed {success_count} events to Firebase.")
            
        time.sleep(SYNC_INTERVAL)

def start_sync_thread():
    """Start the background synchronization thread."""
    t = threading.Thread(target=sync_pending_events, daemon=True)
    t.start()
    return t
