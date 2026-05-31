# ================================================================
#  config.py — ALL settings live here. Edit this file only.
# ================================================================

# ── Telegram Bot ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8663159093:AAFnlh7PkMzKEYoZky3Uretg90-Xuvt90Nc"
TELEGRAM_CHAT_ID   = "7123390454"

# ── Gmail (free email alerts with image) ─────────────────────────
SENDER_EMAIL     = "ddivyasshri@gmail.com"
SENDER_PASSWORD  = "tsjz bfao ntty iibe"

# ── Caregiver 1 ──────────────────────────────────────────────────
CAREGIVER_1 = {
    "name"  : "Divyashri",
    "phone" : "8861369448",
    "email" : "akashkrishna7890@gmail.com"
}

# ── Caregiver 2 ──────────────────────────────────────────────────
CAREGIVER_2 = {
    "name"  : "Shri",
    "phone" : "8762569447",
    "email" : "akashkrishnar10@gmail.com"
}

# ── Emergency backup ──────────────────────────────────────────────
EMERGENCY_PHONE = "9538867028"

# ── Location tag ──────────────────────────────────────────────────
LOCATION_TAG = "Living Room"

# ── Fall detection thresholds ─────────────────────────────────────
TRUNK_ANGLE_THRESHOLD  = 55
HIP_DROP_SPEED_THRESH  = 0.12
STILLNESS_FRAMES       = 25
ALERT_COOLDOWN_SECS    = 30

# ── Voice assistant ───────────────────────────────────────────────
VOICE_COUNTDOWN_SECS   = 10
OKAY_PHRASES = [
    "ok", "i'm okay", "im okay",
    "i am okay", "k", "good",
    "i'm fine", "im fine", "okay",
    "cancel", "stop", "fine", "yes"
]


# ── Paths ─────────────────────────────────────────────────────────
DB_PATH       = "database/fall_detection.db"
SNAPSHOT_DIR  = "assets/snapshots"