"""
setup_patient.py
Run this once before starting the system to add patient profiles.
Usage: python setup_patient.py
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from database.db import init_db, add_patient, get_all_patients, get_fall_history


def prompt(label, default=None):
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val if val else default


def add_new_patient():
    print("\n" + "="*50)
    print("  Add New Patient")
    print("="*50)
    name   = prompt("Full name")
    age    = prompt("Age")
    bg     = prompt("Blood group (e.g. B+)")
    conds  = prompt("Medical conditions (e.g. diabetes, hypertension)")
    meds   = prompt("Current medications")
    cg1n   = prompt("Caregiver 1 name")
    cg1p   = prompt("Caregiver 1 phone (+91XXXXXXXXXX)")
    cg2n   = prompt("Caregiver 2 name")
    cg2p   = prompt("Caregiver 2 phone (+91XXXXXXXXXX)")
    loc    = prompt("Room / location tag", "Living Room")

    pid = add_patient(name, int(age), bg, conds, meds,
                      cg1n, cg1p, cg2n, cg2p, loc)
    print(f"\n  ✓ Patient '{name}' saved. ID = {pid}")
    print(f"  Use this ID when starting the detector: python main.py --patient {pid}\n")
    return pid


def list_patients():
    rows = get_all_patients()
    if not rows:
        print("\n  No patients registered yet.\n")
        return
    print("\n" + "="*70)
    print(f"  {'ID':<4} {'Name':<20} {'Age':<5} {'Blood':<6} {'Location':<15}")
    print("="*70)
    for r in rows:
        print(f"  {r[0]:<4} {r[1]:<20} {r[2]:<5} {r[3]:<6} {r[10]:<15}")
    print()


def view_fall_history(pid):
    rows = get_fall_history(pid)
    if not rows:
        print(f"\n  No fall history for patient ID {pid}.\n")
        return
    print(f"\n  Fall history for patient {pid}:")
    print("="*60)
    for r in rows:
        status = "CANCELLED (said OK)" if r[3] else "CONFIRMED"
        print(f"  {r[0]}  |  {r[1]}  |  conf:{r[2]:.0%}  |  {status}")
    print()


def main():
    init_db()
    while True:
        print("\n" + "="*40)
        print("  Patient Manager")
        print("="*40)
        print("  [1] Add new patient")
        print("  [2] List all patients")
        print("  [3] View fall history for a patient")
        print("  [4] Exit")
        print("="*40)
        choice = input("  Choice: ").strip()

        if choice == "1":
            add_new_patient()
        elif choice == "2":
            list_patients()
        elif choice == "3":
            pid = input("  Patient ID: ").strip()
            view_fall_history(int(pid))
        elif choice == "4":
            break
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
