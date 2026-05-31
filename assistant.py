"""
voice/assistant.py
Speaks fall alerts out loud and listens for "I'm okay" to cancel.
Uses pyttsx3 (offline TTS) + SpeechRecognition (Google STT).

Install: pip install pyttsx3 SpeechRecognition pyaudio
"""

import pyttsx3
import speech_recognition as sr
import threading
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import VOICE_COUNTDOWN_SECS, OKAY_PHRASES


class VoiceAssistant:
    def __init__(self):
        self._init_tts()
        self.recognizer   = sr.Recognizer()
        self.recognizer.energy_threshold        = 200
        self.recognizer.dynamic_energy_threshold = True
        self._cancelled   = False
        self._listening   = False

    def _init_tts(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 155)    # slightly slower — clear for elderly
            self.engine.setProperty("volume", 1.0)
            # Pick a clear voice if available
            voices = self.engine.getProperty("voices")
            for v in voices:
                if "english" in v.name.lower() or "en" in v.id.lower():
                    self.engine.setProperty("voice", v.id)
                    break
            self._tts_available = True
        except Exception as e:
            print(f"[VOICE] TTS init failed: {e} — continuing without speech.")
            self._tts_available = False

    def speak(self, text: str):
        print(f"[VOICE] {text}")
        if not self._tts_available:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"[VOICE] Speak error: {e}")

    def _listen_for_okay(self, on_cancelled):
        """
        Runs in a background thread.
        Listens continuously until OKAY_PHRASES heard or timeout.
        """
        self._listening  = True
        self._cancelled  = False
        deadline         = time.time() + VOICE_COUNTDOWN_SECS

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            while time.time() < deadline and self._listening:
                try:
                    remaining = max(1, int(deadline - time.time()))
                    audio = self.recognizer.listen(source, timeout=remaining,
                                                   phrase_time_limit=4)
                    text  = self.recognizer.recognize_google(audio).lower()
                    print(f"[VOICE] Heard: '{text}'")

                    if any(phrase in text for phrase in OKAY_PHRASES):
                        self._cancelled = True
                        self._listening = False
                        self.speak("Okay. Alert cancelled. Stay safe.")
                        on_cancelled()
                        return

                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    print(f"[VOICE] Listen error: {e}")
                    break

        self._listening = False

    def announce_fall_and_listen(self, location: str,
                                  on_cancelled,
                                  on_timeout):
        """
        Main entry point called when fall is detected.
        1. Speaks the alert loudly.
        2. Starts listening thread.
        3. Counts down — if no cancellation, calls on_timeout.
        """
        self._cancelled = False

        # Announce
               # Announce
        msg = (
            f"Fall detected. Say okay to cancel. "
            f"Alerting in {VOICE_COUNTDOWN_SECS} seconds."
        )
        self.speak(msg)

        # Start listening in background
        listen_thread = threading.Thread(
            target=self._listen_for_okay,
            args=(on_cancelled,),
            daemon=True
        )
        listen_thread.start()

        # Countdown in main flow
        def countdown():
            time.sleep(VOICE_COUNTDOWN_SECS + 1)
            if not self._cancelled:
                self.speak("No response received. Alerting caregivers now.")
                on_timeout()

        countdown_thread = threading.Thread(target=countdown, daemon=True)
        countdown_thread.start()

    def stop_listening(self):
        self._listening = False
