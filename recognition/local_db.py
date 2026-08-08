"""
local_db.py — SQLite Local Database Setup and Operations
=========================================================
"""

import sqlite3
import os
import datetime

os.makedirs("../data", exist_ok=True)
DB_PATH = "../data/local_attendance.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            id_card_code TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT REFERENCES students(student_id),
            event_type TEXT CHECK(event_type IN ('entry', 'exit')),
            timestamp TEXT,
            synced INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mismatch_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_card_id TEXT,
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

def register_student(student_id: str, name: str, department: str, id_card_code: str = None) -> None:
    if id_card_code is None:
        id_card_code = student_id
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO students (student_id, name, department, id_card_code)
        VALUES (?, ?, ?, ?)
    ''', (student_id, name, department, id_card_code))
    conn.commit()
    conn.close()

def get_student(student_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def determine_event_type(student_id: str) -> str:
    today_prefix = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT event_type FROM attendance_events 
        WHERE student_id = ? AND timestamp LIKE ?
        ORDER BY timestamp DESC LIMIT 1
    ''', (student_id, f"{today_prefix}%"))
    row = cursor.fetchone()
    conn.close()

    if row:
        return 'exit' if row['event_type'] == 'entry' else 'entry'
    return 'entry'

def insert_attendance_event(student_id: str) -> dict:
    """Insert into attendance_events and return dict representation."""
    event_type = determine_event_type(student_id)
    now = datetime.datetime.now().isoformat()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attendance_events (student_id, event_type, timestamp, synced)
        VALUES (?, ?, ?, 0)
    ''', (student_id, event_type, now))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()

    student = get_student(student_id)
    name = student['name'] if student else "Unknown"

    return {
        'event_id': event_id,
        'student_id': student_id,
        'name': name,
        'event_type': event_type,
        'timestamp': now,
        'table': 'attendance_events'
    }

def insert_mismatch_log(card_id: str, reason: str) -> dict:
    now = datetime.datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mismatch_logs (scanned_card_id, reason, timestamp, synced)
        VALUES (?, ?, ?, 0)
    ''', (card_id, reason, now))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        'log_id': log_id,
        'scanned_card_id': card_id,
        'reason': reason,
        'timestamp': now,
        'table': 'mismatch_logs'
    }

def get_unsynced_events() -> list[dict]:
    """Return a combined list of unsynced attendance and mismatch events."""
    conn = get_connection()
    cursor = conn.cursor()
    
    events = []
    
    # Get attendance events
    cursor.execute('''
        SELECT a.event_id, a.student_id, a.event_type, a.timestamp, s.name 
        FROM attendance_events a
        LEFT JOIN students s ON a.student_id = s.student_id
        WHERE a.synced = 0
    ''')
    for row in cursor.fetchall():
        d = dict(row)
        d['table'] = 'attendance_events'
        events.append(d)
        
    # Get mismatch logs
    cursor.execute('''
        SELECT log_id, scanned_card_id, reason, timestamp
        FROM mismatch_logs
        WHERE synced = 0
    ''')
    for row in cursor.fetchall():
        d = dict(row)
        d['table'] = 'mismatch_logs'
        events.append(d)
        
    conn.close()
    return events

def mark_as_synced(table: str, row_id: int) -> None:
    """Mark a row in the specified table as synced."""
    conn = get_connection()
    cursor = conn.cursor()
    if table == 'attendance_events':
        cursor.execute("UPDATE attendance_events SET synced = 1 WHERE event_id = ?", (row_id,))
    elif table == 'mismatch_logs':
        cursor.execute("UPDATE mismatch_logs SET synced = 1 WHERE log_id = ?", (row_id,))
    conn.commit()
    conn.close()
