# **Fall Detection System**

#### AI-powered elderly fall detection with voice assistant **and** escalating emergency alerts



#### **What this does**

* **Monitors a person using webcam or pre-recorded video**
* **Detects falls using:**

&#x20;         **trunk angle analysis,**

&#x20;         **hip drop speed,**

&#x20;         **and stillness confirmation**

* **Announces:**
* **“Fall detected. Say ‘I am okay’ to cancel.”**
* **Listens for cancellation phrases using speech recognition**
* **If no response is received:**

&#x20;         **alerts Caregiver 1,**

&#x20;         **escalates to Caregiver 2,**

&#x20;         **then triggers emergency-level alerts**

* **Sends Telegram and Email notifications with snapshots**
* **Stores patient data, fall history, and alert logs in SQLite**
* **Supports privacy-aware stick-figure monitoring**





#### **Main Features**

* **Real-time pose detection using MediaPipe**
* **Multi-signal fall confirmation logic**
* **Voice-based false alarm cancellation**
* **Escalating emergency alert chain**
* **Stick-figure privacy mode**
* **Snapshot capture during fall events**
* **SQLite database logging**
* **Modular project architecture**





##### **Setup — do this in order**



###### **Step 1 — Install dependencies**

***pip install -r requirements.txt***



**If pyaudio fails on Windows:**

***pip install pipwin \&\& pipwin install pyaudio***



###### **Step 2 — Configure alerts**



**Open *config.py* and update:**



***TELEGRAM\_BOT\_TOKEN = "your\_bot\_token"***

***TELEGRAM\_CHAT\_ID   = "your\_chat\_id"***



***SENDER\_EMAIL       = "your\_email@gmail.com"***

***SENDER\_PASSWORD    = "your\_app\_password"***



**Also update caregiver details if needed.**



###### **Step 3 — Add a patient profile**

***python setup_patient.py***

or

***py -3.10 setup_patient.py



**Choose:**



**\[1] Add new patient**



**Save the patient ID shown after registration.**

###### 

###### **Step 4 — Run the system**

***py main.py --patient 1***



**Or:**



***python main.py***



**It will ask for the patient ID.**



#### **Controls during runtime**

**Key	Action**

***Q*	Quit**

***S*	Switch between webcam and video**

***T*	Toggle stick figure / real view**

***P*	Print patient details**





#### **Project Structure**

***fall\_detection/***

***├── main.py                  ← main application***

***├── setup\_patient.py         ← patient manager***

***├── config.py                ← system settings***

***├── requirements.txt***

***│***

***├── core/***

***│   └── detector.py          ← fall detection logic + rendering***

***│***

***├── alerts/***

***│   └── alert\_chain.py       ← Telegram + email escalation***

***│***

***├── voice/***

***│   └── assistant.py         ← voice assistant + speech recognition***

***│***

***├── database/***

***│   └── db.py                ← SQLite database operations***

***│***

***└── assets/***

&#x20;   ***└── snapshots/           ← saved fall snapshots***





#### **Detection Logic**



**The system confirms a possible fall using multiple signals:**



* **Trunk angle deviation from vertical posture**
* **Sudden downward hip movement**
* **Stillness across multiple frames**



**This reduces false positives from:**



* **sitting,**
* **bending,**
* **or temporary posture changes.**



#### **Accuracy Notes**

* **Controlled lighting + full body visibility → \~93–95% accuracy**
* **Voice cancellation significantly reduces false alarms**
* **Lightweight enough for edge-device deployment**



#### **Future Improvements**

* **Machine learning classifier for improved accuracy**
* **Multi-person tracking**
* **Mobile caregiver application**
* **Cloud dashboard**
* **Real acknowledgement system**
* **Raspberry Pi optimization**

