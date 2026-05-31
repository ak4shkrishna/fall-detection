import threading
import time
import smtplib
import requests
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import (
    SENDER_EMAIL, SENDER_PASSWORD,
    CAREGIVER_1, CAREGIVER_2,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
from database.db import log_alert


def send_telegram(message: str, image_path: str = None):
    """Send Telegram message with optional image."""
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(image_path, "rb") as img:
                r = requests.post(url, data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": message
                }, files={"photo": img}, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            r = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
        data = r.json()
        if data.get("ok"):
            print(f"[TELEGRAM] Message sent successfully")
        else:
            print(f"[TELEGRAM] Failed: {data}")
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")


def send_email(to_email: str, subject: str,
               body: str, image_path: str = None):
    try:
        msg = MIMEMultipart()
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-Disposition", "attachment",
                               filename=os.path.basename(image_path))
                msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"[EMAIL] Sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL] Error: {e}")


def format_message(patient_name, location, timestamp, level):
    tag = {
        "caregiver_1": "⚠️ FALL ALERT",
        "caregiver_2": "🚨 ESCALATED FALL ALERT",
        "emergency"  : "🆘 EMERGENCY"
    }.get(level, "FALL ALERT")
    return (
        f"{tag}\n"
        f"Patient  : {patient_name}\n"
        f"Location : {location}\n"
        f"Time     : {timestamp}\n"
        f"Please respond immediately."
    )


class AlertChain:
    def __init__(self):
        self._active       = False
        self._acknowledged = False
        self._thread       = None

    def fire(self, fall_event_id, location, timestamp,
             patient_name, stick_path, real_photo_path):
        if self._active:
            return
        self._active       = True
        self._acknowledged = False
        self._thread = threading.Thread(
            target=self._run,
            args=(fall_event_id, location, timestamp,
                  patient_name, stick_path, real_photo_path),
            daemon=True
        )
        self._thread.start()

    def cancel(self):
        self._active       = False
        self._acknowledged = True
        print("[ALERT] Cancelled by person.")

    def acknowledge(self):
        self._active       = False
        self._acknowledged = True

    def _run(self, fall_event_id, location, timestamp,
             patient_name, stick_path, real_photo_path):

        # ── Level 1: Caregiver 1 ────────────────────────────────
        print(f"\n[CHAIN] Level 1 — alerting {CAREGIVER_1['name']}")
        msg = format_message(patient_name, location, timestamp, "caregiver_1")
        send_telegram(msg, stick_path)
        send_email(CAREGIVER_1["email"],
                   f"FALL ALERT — {patient_name}", msg, stick_path)
        log_alert(fall_event_id, "caregiver_1", CAREGIVER_1["phone"])

        for _ in range(30):
            if self._acknowledged:
                self._active = False
                return
            time.sleep(1)

        if not self._active:
            return

        # ── Level 2: Caregiver 2 ────────────────────────────────
        print(f"\n[CHAIN] Level 2 — alerting {CAREGIVER_2['name']}")
        msg = format_message(patient_name, location, timestamp, "caregiver_2")
        send_telegram(msg, stick_path)
        send_email(CAREGIVER_2["email"],
                   f"ESCALATED FALL ALERT — {patient_name}", msg, stick_path)
        log_alert(fall_event_id, "caregiver_2", CAREGIVER_2["phone"])

        for _ in range(30):
            if self._acknowledged:
                self._active = False
                return
            time.sleep(1)

        if not self._active:
            return

        # ── Level 3: Emergency ───────────────────────────────────
        print(f"\n[CHAIN] EMERGENCY LEVEL")
        msg = format_message(patient_name, location, timestamp, "emergency")
        send_telegram(msg, real_photo_path)
        send_email(CAREGIVER_1["email"],
                   f"EMERGENCY — {patient_name}", msg, real_photo_path)
        send_email(CAREGIVER_2["email"],
                   f"EMERGENCY — {patient_name}", msg, real_photo_path)
        log_alert(fall_event_id, "emergency", "telegram")

        self._active = False
        print("[CHAIN] Emergency chain done.")