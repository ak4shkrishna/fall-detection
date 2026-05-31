"""
dashboard/app.py  —  Run this separately: python -m dashboard.app
Always on. Shows fall history and patient info even when main.py is stopped.
Live feed and metrics appear only when main.py is running.
"""

from flask import Flask, Response, render_template, jsonify, send_file
import cv2
import json
import os
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.db import init_db, get_patient, get_fall_history

app = Flask(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
FRAME_FILE = os.path.join(os.path.dirname(__file__), "live_frame.jpg")

# Record server start time to calculate system uptime
START_TIME = time.time()


def read_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"online": False}


def generate_frames():
    while True:
        state = read_state()
        if not state.get("online") or not os.path.exists(FRAME_FILE):
            time.sleep(0.1)
            continue
        try:
            with open(FRAME_FILE, "rb") as f:
                frame_bytes = f.read()
            if len(frame_bytes) > 0:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
        except Exception:
            pass
        time.sleep(1 / 15)


@app.route("/")
def index():
    state = read_state()
    patient_id = state.get("patient_id", 1)
    patient = get_patient(patient_id)
    return render_template("index.html", patient=patient)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    state = read_state()
    uptime = round(time.time() - START_TIME)

    if not state.get("online"):
        return jsonify({"online": False, "uptime": uptime}), 200

    trunk_angle = state.get("trunk_angle", 0.0)
    fall_state  = state.get("fall_state", "normal")

    if fall_state == "fall" or state.get("fall_active", False):
        posture_label = "FALLEN"
    elif trunk_angle > 45:
        posture_label = "BENDING"
    else:
        posture_label = "STANDING"

    return jsonify({
        "online":        True,
        "fall_active":   state.get("fall_active", False),
        "countdown":     state.get("countdown_val", 0),
        "trunk_angle":   trunk_angle,
        "confidence":    round(state.get("confidence", 0.0) * 100, 1),
        "source_label":  state.get("source_label", "—"),
        "fall_state":    fall_state,
        "posture_label": posture_label,
        "uptime":        uptime,
    })


@app.route("/api/falls/<int:patient_id>")
def api_falls(patient_id):
    try:
        rows = get_fall_history(patient_id)
        falls = []
        for i, r in enumerate(rows):
            falls.append({
                "id":         i + 1,
                "timestamp":  r[0],
                "location":   r[1],
                "confidence": round((r[2] or 0) * 100, 1),
                "cancelled":  bool(r[3]),
                "snapshot":   None,
            })
        return jsonify(falls)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/patient/<int:patient_id>")
def api_patient(patient_id):
    p = get_patient(patient_id)
    if not p:
        return jsonify({}), 404
    return jsonify({
        "id": p[0], "name": p[1], "age": p[2],
        "blood_group": p[3], "conditions": p[4],
        "medications": p[5], "cg1_name": p[6],
        "cg1_phone": p[7], "cg2_name": p[8],
        "cg2_phone": p[9], "location": p[10],
    })


def run_dashboard(host="0.0.0.0", port=5000):
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    init_db()
    print("\n  Dashboard running at http://localhost:5000")
    print("  Start main.py in another terminal for live feed\n")
    run_dashboard()
