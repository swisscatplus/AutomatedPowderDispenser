"""
Petit script de diagnostic pour la balance Mettler Toledo (classe WM).
Usage: python TESTWM.py --config config/settings.json
"""

import argparse
import json
import time
import sys
from automated_arm.Class_WM import WM   # import propre si ton fichier est "Class_WM.py"
import serial


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", "-c",
        default="config/settings.json",   # chemin corrigé
        help="Fichier JSON de config"
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    wm_cfg = cfg.get("wm", {})
    port = wm_cfg.get("port", "COM5")
    baud = wm_cfg.get("baudrate", 9600)
    timeout = wm_cfg.get("timeout", 1.0)

    print(f"Ouverture du port {port} à {baud} bauds (timeout={timeout}s)")
    try:
        bal = WM(port=port, baudrate=baud, timeout=timeout)
    except Exception as e:
        print("❌ Erreur à l'ouverture du port série :", e)
        sys.exit(2)

    try:
        print("\n--- RESET ---")
        try:
            r = bal.reset()
            print("reset ->", repr(r))
        except Exception as e:
            print("reset échoué :", e)

        """print("\n--- Test OUVERTURE PORTE ---")
        try:
            r = bal.open_door()
            print("open_door ->", repr(r))
        except Exception as e:
            print("open_door échoué :", e)


        time.sleep(1.0)"""

        print("\n--- TARE ---")
        try:
            r = bal.tare()
            print("tare ->", repr(r))
        except Exception as e:
            print("tare échoué :", e)

        time.sleep(1.0)

        """print("\n--- ZERO ---")
        try:
            r = bal.zero()
            print("zero ->", repr(r))
        except Exception as e:
            print("zero échoué :", e)

        time.sleep(1.0)

        print("\n--- LECTURE POIDS ---")
        try:
            w = bal.get_weight()
            print("weight ->", w)
        except Exception as e:
            print("get_weight échoué :", e)

        print("\n--- TEST A10 (target + tol) ---")
        try:
            print("set target 5 mg ->", bal.set_target_weight(5, "mg"))
            print("set tol upper 2% ->", bal.set_tolerance_upper(2, "%"))
            print("set tol lower 1% ->", bal.set_tolerance_lower(1, "%"))
        except Exception as e:
            print("A10 failed :", e)

        time.sleep(1.0)

        print("\n--- Test FERMETURE PORTE ---")
        try:
            r = bal.close_door()
            print("close_door ->", repr(r))
        except Exception as e:
            print("close_door échoué :", e)"""

    finally:
        print("\nFermeture du port série")
        bal.close()


if __name__ == "__main__":
    main()
