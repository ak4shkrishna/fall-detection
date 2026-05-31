"""
Run this standalone to test your mic + speech recognition.
python mic_test.py
"""
import speech_recognition as sr

r = sr.Recognizer()
r.energy_threshold = 100
r.dynamic_energy_threshold = False
r.pause_threshold = 0.5

print("\n=== Microphone Test ===")
print("Available mics:")
for i, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"  [{i}] {name}")

mic_index = input("\nEnter mic index to use (or press Enter for default): ").strip()
mic_index = int(mic_index) if mic_index else None

print("\nCalibrating for ambient noise... (1 sec)")
with sr.Microphone(device_index=mic_index) as source:
    r.adjust_for_ambient_noise(source, duration=1.0)
    print(f"Energy threshold set to: {r.energy_threshold}")
    print("\nSpeak now — say 'I am okay' (listening for 10 seconds)...\n")
    try:
        audio = r.listen(source, timeout=10, phrase_time_limit=5)
        print("Got audio — sending to Google...")
        text = r.recognize_google(audio)
        print(f"\n>>> Recognised: '{text}'")
    except sr.WaitTimeoutError:
        print(">>> TIMEOUT — mic heard nothing. Check mic permissions or index.")
    except sr.UnknownValueError:
        print(">>> Heard something but couldn't understand. Try speaking louder/closer.")
    except sr.RequestError as e:
        print(f">>> Google STT failed: {e} — check internet connection.")
    except Exception as e:
        print(f">>> Error: {e}")
