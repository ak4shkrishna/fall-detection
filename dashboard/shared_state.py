"""
dashboard/shared_state.py
A simple thread-safe dictionary shared between main.py and the Flask dashboard.
main.py writes to it; the dashboard reads from it.
"""
import threading

_lock = threading.Lock()
_state = {
    "frame":        None,
    "fall_active":  False,
    "countdown_val": 0,
    "trunk_angle":  0.0,
    "confidence":   0.0,
    "source_label": "Webcam",
    "fall_state":   "normal",
    "patient_id":   1,
}


class _State:
    def get(self, key, default=None):
        with _lock:
            return _state.get(key, default)

    def set(self, key, value):
        with _lock:
            _state[key] = value

    def update(self, d: dict):
        with _lock:
            _state.update(d)


state = _State()
