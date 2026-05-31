import cv2
import numpy as np
import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    TRUNK_ANGLE_THRESHOLD, HIP_DROP_SPEED_THRESH,
    STILLNESS_FRAMES, SNAPSHOT_DIR
)

import mediapipe as mp

_pose_module    = mp.solutions.pose
_drawing_module = mp.solutions.drawing_utils

C_GREEN  = (0, 220, 100)
C_RED    = (30, 30, 220)
C_YELLOW = (0, 210, 255)
C_WHITE  = (255, 255, 255)
C_ORANGE = (0, 140, 255)


def lm_px(landmarks, idx, w, h):
    l = landmarks[idx]
    return np.array([l.x * w, l.y * h])


def trunk_angle_from_vertical(landmarks, w, h):
    mid_s = (lm_px(landmarks, 11, w, h) + lm_px(landmarks, 12, w, h)) / 2
    mid_h = (lm_px(landmarks, 23, w, h) + lm_px(landmarks, 24, w, h)) / 2
    trunk = mid_s - mid_h
    vert  = np.array([0.0, -1.0])
    cos_a = np.dot(trunk, vert) / (np.linalg.norm(trunk) * np.linalg.norm(vert) + 1e-6)
    angle = np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0)))
    return angle, mid_h


def render_stick_figure(frame, results, fall_state):
    h, w = frame.shape[:2]
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    if not results.pose_landmarks:
        cv2.putText(canvas, "No person in frame", (w//2 - 120, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, C_YELLOW, 2)
        return canvas
    color = C_RED if fall_state == "fall" else \
            C_ORANGE if fall_state == "warning" else C_GREEN
    dot_spec  = _drawing_module.DrawingSpec(color=color, thickness=-1, circle_radius=5)
    line_spec = _drawing_module.DrawingSpec(color=color, thickness=2)
    _drawing_module.draw_landmarks(
        canvas,
        results.pose_landmarks,
        _pose_module.POSE_CONNECTIONS,
        dot_spec,
        line_spec
    )
    landmarks = results.pose_landmarks.landmark
    nose = lm_px(landmarks, 0, w, h)
    label = {"fall": "FALL", "warning": "!", "normal": ""}.get(fall_state, "")
    if label:
        cv2.putText(canvas, label,
                    (int(nose[0]) - 20, int(nose[1]) - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    return canvas


def save_snapshots(real_frame, stick_frame):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stick_path = os.path.join(SNAPSHOT_DIR, f"stick_{ts}.jpg")
    real_path  = os.path.join(SNAPSHOT_DIR, f"real_{ts}.jpg")
    cv2.imwrite(stick_path, stick_frame)
    cv2.imwrite(real_path, real_frame)
    print(f"[SNAPSHOT] Saved: {stick_path} | {real_path}")
    return stick_path, real_path


class FallDetector:
    def __init__(self):
        self.prev_hip_y      = None
        self.low_frames      = 0
        self.last_alert_time = 0

    def reset(self):
        self.prev_hip_y = None
        self.low_frames = 0

    @property
    def confidence(self):
        return min(self.low_frames / STILLNESS_FRAMES, 1.0)

    def update(self, trunk_angle, hip_y, frame_h):
        hip_norm       = hip_y / frame_h
        hip_drop_speed = 0.0
        if self.prev_hip_y is not None:
            hip_drop_speed = hip_norm - self.prev_hip_y
        self.prev_hip_y = hip_norm
        tilted   = trunk_angle > TRUNK_ANGLE_THRESHOLD
        dropping = hip_drop_speed > HIP_DROP_SPEED_THRESH
        if tilted or dropping:
            self.low_frames += 1
        else:
            self.low_frames = max(0, self.low_frames - 1)
        now = time.time()
        if (self.low_frames >= STILLNESS_FRAMES and
                now - self.last_alert_time > 60):
            self.last_alert_time = now
            self.low_frames = 0
            return True
        return False

    def get_state(self, trunk_angle):
        if self.low_frames >= STILLNESS_FRAMES * 0.8:
            return "fall"
        if self.low_frames >= STILLNESS_FRAMES * 0.4 or \
                trunk_angle > TRUNK_ANGLE_THRESHOLD:
            return "warning"
        return "normal"


def draw_hud(canvas, trunk_angle, detector,
             source_label, location,
             fall_active, countdown):
    h, w = canvas.shape[:2]

    TOP    = 40
    BOTTOM = 50

    # ── Border ───────────────────────────────────────────────────
    border_color = (0, 0, 220) if fall_active else (0, 200, 80)
    cv2.rectangle(canvas, (0, 0), (w-1, h-1), border_color, 5)

    # ── TOP BAR ──────────────────────────────────────────────────
    cv2.rectangle(canvas, (0, 0), (w, TOP), (20, 20, 20), -1)

    if trunk_angle < 30:
        posture = "STANDING"
        p_color = C_GREEN
    elif trunk_angle < 60:
        posture = "BENDING"
        p_color = C_ORANGE
    else:
        posture = "FALLEN"
        p_color = C_RED

    

    # Posture — far right (no overlap)
    cv2.putText(canvas,                  f"Posture: {posture}",
                (w - 240, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.52, p_color, 1)

    # ── BOTTOM BAR ───────────────────────────────────────────────
    cv2.rectangle(canvas, (0, h - BOTTOM), (w, h), (20, 20, 20), -1)

    if fall_active:
        cv2.rectangle(canvas, (0, h - BOTTOM), (w, h), (0, 0, 200), -1)
        cv2.putText(canvas, "FALL DETECTED",
                    (10, h - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, C_WHITE, 2)
        if countdown > 0:
            cv2.putText(canvas, f"Say 'I am okay' to cancel — {countdown}s",
                        (10, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, C_YELLOW, 1)
        else:
            cv2.putText(canvas, "Alerting caregivers...",
                        (10, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, C_RED, 1)
    else:
        # Confidence label
        cv2.putText(canvas, "Fall Probability:",
                    (10, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, C_WHITE, 1)
        # Bar
        bar_x = 120
        bar_w = w - 200
        bar_y = h - 36
        cv2.rectangle(canvas, (bar_x, bar_y),
                      (bar_x + bar_w, bar_y + 20), (55, 55, 55), -1)
        fill = int(detector.confidence * bar_w)
        bar_c = C_RED if detector.confidence > 0.75 else C_ORANGE
        if fill > 0:
            cv2.rectangle(canvas, (bar_x, bar_y),
                          (bar_x + fill, bar_y + 20), bar_c, -1)
        # Percentage
        cv2.putText(canvas, f"{int(detector.confidence*100)}%",
                    (bar_x + bar_w + 8, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_WHITE, 1)