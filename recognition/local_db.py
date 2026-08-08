"""
local_db.py — SQLite Local Database Setup and Operations
=========================================================
"""

import sqlite3
import os
import datetime

# Ensure data directory exists
os.makedirs("../data", exist_ok=True)
DB_PATH = "../data/local_attendance.db"

def get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection to the local DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            registered_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT REFERENCES students(student_id),
            event_type TEXT CHECK(event_type IN ('entry', 'exit')),
            timestamp TEXT,
            synced INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proxy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT,
            reason TEXT,
            timestamp TEXT,
            synced INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safety_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_type TEXT,
            value REAL,
            unit TEXT,
            timestamp TEXT,
            synced INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def register_student(student_id: str, name: str, department: str) -> None:
    """Insert a new student record."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO students (student_id, name, department, registered_at)
        VALUES (?, ?, ?, ?)
    ''', (student_id, name, department, now))
    conn.commit()
    conn.close()

def get_student(student_id: str) -> dict | None:
    """Fetch student info by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def determine_event_type(student_id: str) -> str:
    """
    Check today's logs for this student and return 'entry' or 'exit'.
    """
    today_prefix = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT event_type FROM attendance_logs 
        WHERE student_id = ? AND timestamp LIKE ?
        ORDER BY timestamp DESC LIMIT 1
    ''', (student_id, f"{today_prefix}%"))
    row = cursor.fetchone()
    conn.close()

    if row:
        last_event = row['event_type']
        return 'exit' if last_event == 'entry' else 'entry'
    return 'entry'

def log_event(student_id: str) -> dict:
    """
    Determine event_type, insert a new attendance_log row, and return the full event dict.
    """
    event_type = determine_event_type(student_id)
    now = datetime.datetime.now().isoformat()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attendance_logs (student_id, event_type, timestamp, synced)
        VALUES (?, ?, ?, 0)
    ''', (student_id, event_type, now))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Get student name for the event dict
    student = get_student(student_id)
    name = student['name'] if student else "Unknown"

    return {
        'id': log_id,
        'student_id': student_id,
        'name': name,
        'event_type': event_type,
        'timestamp': now
    }

def log_proxy_event(card_id: str, reason: str) -> dict:
    """
    Log a mismatch or proxy attempt.
    """
    now = datetime.datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO proxy_logs (card_id, reason, timestamp, synced)
        VALUES (?, ?, ?, 0)
    ''', (card_id, reason, now))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        'id': log_id,
        'card_id': card_id,
        'reason': reason,
        'timestamp': now
    }

def get_unsynced_events() -> list[dict]:
    """Return all unsynced attendance logs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.name FROM attendance_logs a
        LEFT JOIN students s ON a.student_id = s.student_id
        WHERE a.synced = 0
    ''')
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def mark_synced(log_id: int) -> None:
    """Set synced = 1 for a given log ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE attendance_logs SET synced = 1 WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
