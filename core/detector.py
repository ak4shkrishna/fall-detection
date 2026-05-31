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

# ── Colour palette ────────────────────────────────────────────────────────────
C_GREEN   = (80, 220, 100)
C_RED     = (60,  60, 230)
C_YELLOW  = (40, 210, 255)
C_WHITE   = (255, 255, 255)
C_ORANGE  = (40, 160, 255)
C_ACCENT  = (100, 230, 100)   # neon green
C_DARK    = (15,  18,  22)
C_PANEL   = (22,  26,  32)
C_MUTED   = (100, 110, 125)
C_DANGER  = (55,  60, 240)
C_WARN    = (30, 160, 255)


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
        self.prev_hip_y      = None
        self.low_frames      = 0
        self.last_alert_time = 0   # clear cooldown so next fall triggers immediately

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


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _rounded_rect(img, x1, y1, x2, y2, color, radius=8, thickness=-1, alpha=1.0):
    """Draw a filled rounded rectangle. Single copy for alpha path (perf fix)."""
    corners = [(x1+radius, y1+radius), (x2-radius, y1+radius),
               (x1+radius, y2-radius), (x2-radius, y2-radius)]
    if alpha < 1.0:
        overlay = img.copy()                          # one copy, not four
        cv2.rectangle(overlay, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
        cv2.rectangle(overlay, (x1, y1 + radius), (x2, y2 - radius), color, thickness)
        for cx, cy in corners:
            cv2.circle(overlay, (cx, cy), radius, color, thickness)
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    else:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, thickness)
        for cx, cy in corners:
            cv2.circle(img, (cx, cy), radius, color, thickness)


def _pill_text(img, text, x, y, bg_color, text_color, scale=0.42, pad_x=10, pad_y=5):
    """Draw pill-shaped label with text."""
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x1, y1 = x, y - th - pad_y
    x2, y2 = x + tw + pad_x * 2, y + pad_y
    _rounded_rect(img, x1, y1, x2, y2, bg_color, radius=6)
    cv2.putText(img, text, (x + pad_x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, text_color, 1, cv2.LINE_AA)


def _progress_bar(img, x, y, w, h, value, color, bg=(40, 45, 52), radius=4):
    """Draw a modern rounded progress bar."""
    _rounded_rect(img, x, y, x + w, y + h, bg, radius=radius)
    fill = int(value * w)
    if fill > radius * 2:
        _rounded_rect(img, x, y, x + fill, y + h, color, radius=radius)


def _semi_rect(canvas, x1, y1, x2, y2, color, alpha=0.72):
    """Draw a semi-transparent filled rectangle."""
    sub = canvas[y1:y2, x1:x2]
    rect = np.full_like(sub, color)
    cv2.addWeighted(rect, alpha, sub, 1 - alpha, 0, sub)
    canvas[y1:y2, x1:x2] = sub


def draw_hud(canvas, trunk_angle, detector, source_label, location,
             fall_active, countdown, cancel_flash=False):
    h, w = canvas.shape[:2]

    accent_col = C_DANGER if fall_active else C_ACCENT

    # ── CONFIDENCE BAR — full-width at very top of frame (3px) ───────────────
    conf_top     = detector.confidence
    conf_top_col = C_DANGER if conf_top > 0.75 else C_WARN if conf_top > 0.4 else C_ACCENT
    cv2.line(canvas, (0, 4), (w, 4), (30, 35, 40), 8)
    fill_top = int(conf_top * w)
    if fill_top > 0:
        cv2.line(canvas, (0, 4), (fill_top, 4), conf_top_col, 8)

    # Confidence % label — just below bar, top-left
    conf_lbl = f"{int(conf_top * 100)}%"
    cv2.putText(canvas, conf_lbl,
                (9, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, conf_lbl,
                (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.32, conf_top_col, 1, cv2.LINE_AA)

    # ── TIMESTAMP — floated top-left, large, directly on video ───────────────
    now_str = datetime.now().strftime("%H:%M:%S")
    cv2.putText(canvas, now_str,
                (9, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(canvas, now_str,
                (8, 53), cv2.FONT_HERSHEY_SIMPLEX, 0.72, C_WHITE, 1, cv2.LINE_AA)

    # ── STATUS PILL — right side, vertically at ~20% height ──────────────────
    if fall_active:
        status_text = "FALL DETECTED"
        s_bg  = (40, 30, 160)
        s_col = (180, 180, 255)
    else:
        status_text = "MONITORING"
        s_bg  = (18, 45, 22)
        s_col = C_ACCENT

    (sw, sh), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
    pill_x = w - sw - 28
    pill_y = 28                          # top-right corner, just below conf bar
    _pill_text(canvas, status_text, pill_x, pill_y,
               bg_color=s_bg, text_color=s_col, scale=0.36)

    # Location + source — small muted line below the pill
    meta = f"{location}  |  {source_label}"
    (mw, _), _ = cv2.getTextSize(meta, cv2.FONT_HERSHEY_SIMPLEX, 0.28, 1)
    cv2.putText(canvas, meta,
                (w - mw - 14, pill_y + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, meta,
                (w - mw - 15, pill_y + 17),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, C_MUTED, 1, cv2.LINE_AA)

    # ── BOTTOM-LEFT metrics — no card box, floated directly on video ─────────
    # Metrics sit 12px from left, stacked up from the footer edge.
    # Each row has a shadow-text pass first for legibility against any bg.
    FOOTER_H = 58   # taller footer: room for alert text + countdown bar
    BAR_W    = 160

    mx  = 16                          # left margin
    my  = h - FOOTER_H - 12          # bottom anchor (just above footer)

    # ── Posture ───────────────────────────────────────────────────────────────
    if trunk_angle < 30:
        posture, p_col = "STANDING", C_ACCENT
    elif trunk_angle < 60:
        posture, p_col = "BENDING",  C_WARN
    else:
        posture, p_col = "FALLEN",   C_DANGER

    cv2.putText(canvas, "POSTURE",
                (mx + 1, my - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, "POSTURE",
                (mx, my - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.28, C_MUTED, 1, cv2.LINE_AA)
    cv2.putText(canvas, posture,
                (mx + 1, my + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, posture,
                (mx, my), cv2.FONT_HERSHEY_SIMPLEX, 0.48, p_col, 1, cv2.LINE_AA)

    my -= 52   # step up for trunk angle row

    # ── Trunk angle ───────────────────────────────────────────────────────────
    angle_col = C_DANGER if trunk_angle > 60 else C_WARN if trunk_angle > 30 else C_ACCENT

    cv2.putText(canvas, "TRUNK ANGLE",
                (mx + 1, my - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, "TRUNK ANGLE",
                (mx, my), cv2.FONT_HERSHEY_SIMPLEX, 0.28, C_MUTED, 1, cv2.LINE_AA)
    cv2.putText(canvas, f"{trunk_angle:.1f} deg",
                (mx + 1, my + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"{trunk_angle:.1f} deg",
                (mx, my + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.50, angle_col, 1, cv2.LINE_AA)

    # Slim progress bar for trunk angle (also no box)
    bar_y2 = my + 24
    cv2.line(canvas, (mx, bar_y2), (mx + BAR_W, bar_y2), (50, 55, 60), 2)
    fill_a = int(min(trunk_angle / 90, 1.0) * BAR_W)
    if fill_a > 0:
        cv2.line(canvas, (mx, bar_y2), (mx + fill_a, bar_y2), angle_col, 2)

    # ── FOOTER alert bar ─────────────────────────────────────────────────────
    if fall_active:
        _semi_rect(canvas, 0, h - FOOTER_H, w, h, (20, 12, 50), alpha=0.90)
        cv2.rectangle(canvas, (0, h - FOOTER_H), (w, h - FOOTER_H + 2), C_DANGER, -1)
        # Row 1 — alert title
        cv2.putText(canvas, "FALL DETECTED  —  ALERTING CAREGIVERS",
                    (12, h - FOOTER_H + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (180, 180, 255), 1, cv2.LINE_AA)
        if countdown > 0:
            # Row 2 — countdown progress bar (clear gap below row 1)
            _progress_bar(canvas, 12, h - FOOTER_H + 30, w - 24, 6,
                          countdown / 15, C_YELLOW)
            # Row 3 — cancel instruction (bottom of footer)
            cv2.putText(canvas, f"Say 'I AM OKAY' to cancel  —  {countdown}s",
                        (12, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, C_YELLOW, 1, cv2.LINE_AA)
        else:
            cv2.putText(canvas, "Alerting caregivers now...",
                        (12, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, C_DANGER, 1, cv2.LINE_AA)
    else:
        # No footer bar — just the key hints as a right-side column
        keys = [
            ("Q", "Quit"),
            ("S", "Switch source"),
            ("T", "Toggle view"),
            ("P", "Patient info"),
        ]
        row_h  = 18
        scale  = 0.30
        font   = cv2.FONT_HERSHEY_SIMPLEX
        total  = len(keys) * row_h
        ky     = h - total - 12
        # Find widest row so all rows share the same left x (right-aligned column)
        max_fw = max(cv2.getTextSize(f"{k}  {l}", font, scale, 1)[0][0] for k, l in keys)
        fx     = w - max_fw - 10
        for key, label in keys:
            # shadow pass
            cv2.putText(canvas, key,
                        (fx + 1, ky + 1), font, scale, (0, 0, 0), 2, cv2.LINE_AA)
            rest = f"  {label}"
            (kw, _), _ = cv2.getTextSize(key, font, scale, 1)
            cv2.putText(canvas, rest,
                        (fx + kw + 1, ky + 1), font, scale, (0, 0, 0), 2, cv2.LINE_AA)
            # key letter in accent, label in muted — same x for every row
            cv2.putText(canvas, key,
                        (fx, ky), font, scale, C_ACCENT, 1, cv2.LINE_AA)
            cv2.putText(canvas, rest,
                        (fx + kw, ky), font, scale, C_MUTED, 1, cv2.LINE_AA)
            ky += row_h

    # ── ALERT CANCELLED flash banner ─────────────────────────────────────────
    if cancel_flash:
        msg = "ALERT CANCELLED"
        sub  = "Stay Safe"
        pad  = 24
        (mw, mh), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        (sw, sh), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        box_w = max(mw, sw) + pad * 2
        box_h = mh + sh + pad * 2 + 10
        bx = (w - box_w) // 2
        by = (h - box_h) // 2
        _semi_rect(canvas, bx, by, bx + box_w, by + box_h, (10, 55, 10), alpha=0.88)
        cv2.rectangle(canvas, (bx, by), (bx + box_w, by + box_h), C_ACCENT, 1)
        # Main text centred
        tx = bx + (box_w - mw) // 2
        cv2.putText(canvas, msg, (tx, by + pad + mh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, C_ACCENT, 2, cv2.LINE_AA)
        # Sub text centred
        sx = bx + (box_w - sw) // 2
        cv2.putText(canvas, sub, (sx, by + pad + mh + 10 + sh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_WHITE, 1, cv2.LINE_AA)

    # ── Outer border ─────────────────────────────────────────────────────────
    border_col = C_DANGER if fall_active else (40, 48, 58)
    cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), border_col, 2)
