"""
voice/assistant.py
"""

import pyttsx3
import speech_recognition as sr
import threading
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import VOICE_COUNTDOWN_SECS

OKAY_PHRASES = [
    "i am okay", "i'm okay", "im okay",
    "i am fine", "i'm fine", "im fine",
    "i am ok", "i'm ok", "im ok",
    "okay", "ok", "fine",
    "i am alright", "i'm alright", "im alright", "alright",
    "cancel", "stop", "no alert", "cancel alert",
    "i am good", "i'm good", "im good", "all good",
]


class VoiceAssistant:
    MIC_INDEX = 0  # Sound Mapper — confirmed working

    def __init__(self):
        self._init_tts()
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.energy_threshold = 100
        self.recognizer.pause_threshold = 0.5
        self._cancelled = False
        self._listening = False

    def _init_tts(self):
        self._tts_available = True   # PowerShell TTS always available on Windows

    def speak(self, text: str):
        print(f"[VOICE] Speaking: {text}")
        try:
            # Use PowerShell TTS — works from any thread, no pyttsx3 blocking
            import subprocess
            clean = text.replace("'", "").replace('"', '')
            subprocess.run(
                ["powershell", "-Command",
                 f"Add-Type -AssemblyName System.Speech; "
                 f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                 f"$s.Rate = 1; $s.Volume = 100; $s.Speak('{clean}');"],
                check=True
            )
        except Exception as e:
            print(f"[VOICE] Speak error: {e}")

    def _matches_okay(self, text: str) -> bool:
        import re
        text = text.lower().strip()
        for phrase in OKAY_PHRASES:
            # Use word boundary so 'ok' doesn't match inside 'anokhi' etc.
            pattern = r'\b' + re.escape(phrase) + r'\b'
            if re.search(pattern, text):
                print(f"[VOICE] ✓ Matched: '{phrase}' in '{text}'")
                return True
        return False

    def _listen_for_okay(self, on_cancelled):
        self._listening = True
        self._cancelled = False
        deadline = time.time() + VOICE_COUNTDOWN_SECS

        print(f"[VOICE] Opening mic index {self.MIC_INDEX}...")
        try:
            mic = sr.Microphone(device_index=self.MIC_INDEX)
        except Exception as e:
            print(f"[VOICE] ERROR opening mic {self.MIC_INDEX}: {e}")
            print("[VOICE] Falling back to default mic")
            mic = sr.Microphone()

        with mic as source:
            # Force a very low threshold — do NOT let adjust_for_ambient_noise raise it
            self.recognizer.energy_threshold = 50
            self.recognizer.dynamic_energy_threshold = False
            print(f"[VOICE] Energy threshold fixed at: {self.recognizer.energy_threshold}")
            print(f"[VOICE] Listening... (deadline in {int(deadline - time.time())}s)")

            attempt = 0
            while time.time() < deadline and self._listening:
                attempt += 1
                remaining = max(1, int(deadline - time.time()))
                print(f"[VOICE] Attempt {attempt} — {remaining}s left, threshold={self.recognizer.energy_threshold:.1f}")
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=2,        # don't wait long for speech to start
                        phrase_time_limit=2  # grab short chunks — faster STT
                    )
                    print(f"[VOICE] Got audio chunk, sending to Google...")
                    text = self.recognizer.recognize_google(
                        audio, language="en-IN"
                    ).lower()
                    print(f"[VOICE] Heard: '{text}'")

                    if self._matches_okay(text):
                        self._cancelled = True
                        self._listening = False
                        on_cancelled()   # cancel instantly, no TTS delay
                        return

                except sr.WaitTimeoutError:
                    print(f"[VOICE] Timeout on attempt {attempt} — no speech detected")
                except sr.UnknownValueError:
                    print(f"[VOICE] Attempt {attempt} — couldn't understand, retrying...")
                except sr.RequestError as e:
                    print(f"[VOICE] Google STT error: {e}")
                except Exception as e:
                    print(f"[VOICE] Unexpected error: {e}")
                    break

        print("[VOICE] Listening loop ended")
        self._listening = False

    def announce_fall_and_listen(self, location: str, on_cancelled, on_timeout):
        self._cancelled = False

        msg = (
            f"Fall detected in {location}. "
            f"Say I am okay or I am fine to cancel. "
            f"Alerting caregivers in {VOICE_COUNTDOWN_SECS} seconds."
        )
        self.speak(msg)

        # Wait for TTS echo to clear before opening mic
        time.sleep(0.8)

        listen_thread = threading.Thread(
            target=self._listen_for_okay,
            args=(on_cancelled,),
            daemon=True
        )
        listen_thread.start()

        def countdown():
            for _ in range(VOICE_COUNTDOWN_SECS + 1):
                if self._cancelled:   # cancelled — bail out immediately
                    return
                time.sleep(1)
            if not self._cancelled:
                self.speak("No response received. Alerting caregivers now.")
                on_timeout()

        threading.Thread(target=countdown, daemon=True).start()

    def stop_listening(self):
        self._listening = False
