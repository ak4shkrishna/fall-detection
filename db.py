"""
database/db.py
All SQLite operations — patients, fall events, alert log.
"""

import sqlite3
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    # ── patients ────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            age                 INTEGER NOT NULL,
            blood_group         TEXT,
            medical_conditions  TEXT,
            medications         TEXT,
            caregiver_1_name    TEXT,
            caregiver_1_phone   TEXT,
            caregiver_2_name    TEXT,
            caregiver_2_phone   TEXT,
            location_tag        TEXT,
            created_at          TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── fall_events ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS fall_events (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER REFERENCES patients(id),
            timestamp        TEXT    DEFAULT (datetime('now','localtime')),
            location_tag     TEXT,
            confidence_score REAL,
            trunk_angle      REAL,
            cancelled        INTEGER DEFAULT 0,   -- 1 = person said I'm okay
            snapshot_stick   TEXT,                -- path to stick figure image
            snapshot_real    TEXT,                -- path to real photo (emergency only)
            notes            TEXT
        )
    """)

    # ── alert_log ───────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            fall_event_id    INTEGER REFERENCES fall_events(id),
            alert_level      TEXT,   -- 'caregiver_1', 'caregiver_2', 'emergency'
            sent_to          TEXT,
            sent_at          TEXT    DEFAULT (datetime('now','localtime')),
            acknowledged     INTEGER DEFAULT 0,
            response_time_secs INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables ready.")


# ── Patient operations ───────────────────────────────────────────

def add_patient(name, age, blood_group, medical_conditions,
                medications, cg1_name, cg1_phone, cg2_name, cg2_phone, location):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO patients
        (name, age, blood_group, medical_conditions, medications,
         caregiver_1_name, caregiver_1_phone,
         caregiver_2_name, caregiver_2_phone, location_tag)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (name, age, blood_group, medical_conditions, medications,
          cg1_name, cg1_phone, cg2_name, cg2_phone, location))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    print(f"[DB] Patient '{name}' added with ID {pid}")
    return pid


def get_all_patients():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients")
    rows = c.fetchall()
    conn.close()
    return rows


def get_patient(patient_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    row = c.fetchone()
    conn.close()
    return row


# ── Fall event operations ────────────────────────────────────────

def log_fall_event(patient_id, location, confidence, trunk_angle,
                   snapshot_stick=None, snapshot_real=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO fall_events
        (patient_id, location_tag, confidence_score, trunk_angle,
         snapshot_stick, snapshot_real)
        VALUES (?,?,?,?,?,?)
    """, (patient_id, location, confidence, trunk_angle,
          snapshot_stick, snapshot_real))
    eid = c.lastrowid
    conn.commit()
    conn.close()
    print(f"[DB] Fall event logged. ID={eid}")
    return eid


def cancel_fall_event(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE fall_events SET cancelled=1 WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    print(f"[DB] Fall event {event_id} marked cancelled (person said OK).")


def get_fall_history(patient_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT timestamp, location_tag, confidence_score, cancelled
        FROM fall_events WHERE patient_id=?
        ORDER BY timestamp DESC
    """, (patient_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# ── Alert log operations ─────────────────────────────────────────

def log_alert(fall_event_id, level, sent_to):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO alert_log (fall_event_id, alert_level, sent_to)
        VALUES (?,?,?)
    """, (fall_event_id, level, sent_to))
    aid = c.lastrowid
    conn.commit()
    conn.close()
    return aid


def acknowledge_alert(alert_id, response_time_secs):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE alert_log
        SET acknowledged=1, response_time_secs=?
        WHERE id=?
    """, (response_time_secs, alert_id))
    conn.commit()
    conn.close()
