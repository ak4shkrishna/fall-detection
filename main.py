import cv2
import mediapipe as mp
import argparse
import time
import sys
import os
import threading
import json
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

from config import LOCATION_TAG
from database.db import init_db, get_patient, log_fall_event, cancel_fall_event
from core.detector import (
    FallDetector, render_stick_figure,
    trunk_angle_from_vertical, draw_hud, save_snapshots
)
from alerts.alert_chain import AlertChain
from voice.assistant import VoiceAssistant

STATE_FILE = os.path.join(os.path.dirname(__file__), "dashboard", "state.json")


def write_state(data: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def choose_source():
    print("\n" + "="*45)
    print("  Fall Detection System — Video Source")
    print("="*45)
    print("  [1] Webcam (front camera, live)")
    print("  [2] Pre-recorded video file")
    print("="*45)
    choice = input("  Enter 1 or 2: ").strip()
    if choice == "1":
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("  ERROR: Cannot open webcam.")
            sys.exit(1)
        return cap, "Webcam"
    elif choice == "2":
        path = input("  Full path to video file: ").strip()
        cap  = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"  ERROR: Cannot open {path}")
            sys.exit(1)
        return cap, os.path.basename(path)
    else:
        print("  Defaulting to webcam.")
        cap = cv2.VideoCapture(0)
        return cap, "Webcam"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patient", type=int, default=None)
    args = parser.parse_args()

    init_db()

    if args.patient:
        patient = get_patient(args.patient)
    else:
        pid = input("\n  Enter patient ID: ").strip()
        patient = get_patient(int(pid))

    if not patient:
        print("  ERROR: Patient not found. Run setup_patient.py first.")
        sys.exit(1)

    patient_id   = patient[0]
    patient_name = patient[1]
    location     = patient[10] or LOCATION_TAG

    print(f"\n  Monitoring: {patient_name} | Location: {location}")
    print("  Q = quit | S = switch source | T = toggle stick/real | P = patient info\n")

    cap, source_label = choose_source()

    pose = mp.solutions.pose.Pose(
        min_detection_confidence=0.65,
        min_tracking_confidence=0.65,
        model_complexity=2
    )

    detector    = FallDetector()
    alert_chain = AlertChain()
    voice       = VoiceAssistant()

    fall_active       = False
    fall_event_id     = None
    countdown_val     = 0
    countdown_start   = 0
    stick_snap        = None
    real_snap         = None
    show_real         = True
    cancel_flash_until = 0   # timestamp until which to show cancelled banner

    def on_cancelled():
        nonlocal fall_active, fall_event_id, cancel_flash_until
        alert_chain.cancel()
        if fall_event_id:
            cancel_fall_event(fall_event_id)
        fall_active        = False
        fall_event_id      = None
        cancel_flash_until = time.time() + 3
        detector.reset()   # clear low_frames so next fall can trigger fresh
        print("[MAIN] Fall cancelled by voice.")

    def on_timeout():
        nonlocal fall_active, fall_event_id
        alert_chain.fire(
            fall_event_id   = fall_event_id,
            location        = location,
            timestamp       = datetime.now().strftime("%d %b %Y, %I:%M %p"),
            patient_name    = patient_name,
            stick_path      = stick_snap,
            real_photo_path = real_snap
        )
        fall_active   = False
        fall_event_id = None
        detector.reset()   # ready for next fall

    # Write initial online state
    write_state({
        "online": True,
        "patient_id": patient_id,
        "fall_active": False,
        "countdown_val": 0,
        "trunk_angle": 0.0,
        "confidence": 0.0,
        "source_label": source_label,
        "fall_state": "normal",
    })

    # ── Create maximized window once, before the loop ─────────────────────────
    import ctypes
    import numpy as _np
    WIN = "Fall Detection System"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    # Show blank frame, pump events, then maximize — reliable sequence
    blank = _np.zeros((720, 1280, 3), dtype=_np.uint8)
    cv2.imshow(WIN, blank)
    for _ in range(5):          # pump a few times so Win32 registers the window
        cv2.waitKey(30)
    hwnd = ctypes.windll.user32.FindWindowW(None, WIN)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 3)   # SW_MAXIMIZE
        ctypes.windll.user32.SetForegroundWindow(hwnd)

    while True:
        ret, frame = cap.read()
        if not ret:
            if source_label != "Webcam":
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            break

        if source_label == "Webcam":
            frame = cv2.flip(frame, 1)

        h, w   = frame.shape[:2]
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(rgb)

        trunk_angle = 0.0
        mid_hip_y   = h // 2

        if result.pose_landmarks:
            lms = result.pose_landmarks.landmark
            trunk_angle, mid_hip = trunk_angle_from_vertical(lms, w, h)
            mid_hip_y = mid_hip[1]

            if not fall_active:
                confirmed = detector.update(trunk_angle, mid_hip_y, h)
                if confirmed:
                    fall_active     = True
                    countdown_val   = 15
                    countdown_start = time.time()
                    fall_state      = detector.get_state(trunk_angle)
                    stick_frame     = render_stick_figure(frame, result, "fall")
                    stick_snap, real_snap = save_snapshots(frame, stick_frame)
                    fall_event_id   = log_fall_event(
                        patient_id      = patient_id,
                        location        = location,
                        confidence      = detector.confidence,
                        trunk_angle     = trunk_angle,
                        snapshot_stick  = stick_snap,
                        snapshot_real   = real_snap
                    )
                    threading.Thread(
                        target=voice.announce_fall_and_listen,
                        args=(location, on_cancelled, on_timeout),
                        daemon=True
                    ).start()

        if fall_active:
            elapsed       = time.time() - countdown_start
            countdown_val = max(0, 15 - int(elapsed))

        fall_state = detector.get_state(trunk_angle) if result.pose_landmarks else "normal"
        if fall_active:
            fall_state = "fall"

        if show_real:
            canvas = frame.copy()
            if result.pose_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(
                    canvas,
                    result.pose_landmarks,
                    mp.solutions.pose.POSE_CONNECTIONS,
                    mp.solutions.drawing_utils.DrawingSpec(
                        color=(0, 255, 0), thickness=2, circle_radius=3),
                    mp.solutions.drawing_utils.DrawingSpec(
                        color=(255, 255, 255), thickness=2)
                )
        else:
            canvas = render_stick_figure(frame, result, fall_state)

        draw_hud(canvas, trunk_angle, detector,
                 source_label, location,
                 fall_active, countdown_val,
                 cancel_flash=time.time() < cancel_flash_until)

        # Save frame for dashboard
        frame_path = os.path.join(os.path.dirname(__file__), "dashboard", "live_frame.jpg")
        cv2.imwrite(frame_path, canvas)

        # Write state for dashboard
        write_state({
            "online":       True,
            "patient_id":   patient_id,
            "fall_active":  fall_active,
            "countdown_val": countdown_val,
            "trunk_angle":  round(trunk_angle, 1),
            "confidence":   round(detector.confidence, 3),
            "source_label": source_label,
            "fall_state":   fall_state,
        })

        # Show native resolution — no resize, window handles scaling
        cv2.imshow(WIN, canvas)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cap.release()
            cap, source_label = choose_source()
            detector.reset()
        elif key == ord('t'):
            show_real = not show_real
            mode = "Real Video" if show_real else "Stick Figure"
            print(f"[MAIN] Switched to {mode}")
        elif key == ord('p'):
            print(f"\n  Patient : {patient_name} | Age: {patient[2]} | Blood: {patient[3]}")
            print(f"  Conditions: {patient[4]} | Meds: {patient[5]}")
            print(f"  Caregiver 1: {patient[6]} {patient[7]}")
            print(f"  Caregiver 2: {patient[8]} {patient[9]}\n")

    # Mark offline when done
    write_state({"online": False})
    cap.release()
    cv2.destroyAllWindows()
    pose.close()
    print("\n[INFO] Session ended.")


if __name__ == "__main__":
    main()
