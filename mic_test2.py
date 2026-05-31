"""
Tests mic indices 0,1,5,9,15 one by one — speak into laptop for each.
Run: python mic_test2.py
"""
import speech_recognition as sr

r = sr.Recognizer()
r.energy_threshold = 50
r.dynamic_energy_threshold = False
r.pause_threshold = 0.5

to_test = [
    (0,  "Sound Mapper (default)"),
    (1,  "Intel Smart Sound"),
    (5,  "Intel Smart Sound Technology"),
    (9,  "Intel Smart Sound Technology (full)"),
    (15, "Realtek HD Audio Mic"),
]

for idx, name in to_test:
    print(f"\n--- Testing [{idx}] {name} ---")
    print("Say 'I am okay' now (5 seconds)...")
    try:
        with sr.Microphone(device_index=idx) as source:
            audio = r.listen(source, timeout=5, phrase_time_limit=4)
            text = r.recognize_google(audio, language="en-IN")
            print(f">>> HEARD: '{text}'  ✓ THIS MIC WORKS — use index {idx}")
            break
    except sr.WaitTimeoutError:
        print(f">>> Timeout — mic {idx} heard nothing")
    except sr.UnknownValueError:
        print(f">>> Heard audio but couldn't understand on mic {idx}")
    except Exception as e:
        print(f">>> Error on mic {idx}: {e}")
