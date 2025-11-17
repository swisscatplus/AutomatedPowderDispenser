"""
Petit script de diagnostic pour la balance Mettler Toledo (classe WM).
Usage: python TESTWM.py --config config/settings.json
"""

import argparse
import json
import time
import sys
import os
from automated_arm.Class_WM import WM
import serial


def load_config(path: str) -> dict:
    """Charge un fichier JSON et renvoie son contenu."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", "-c",
        default="config/settings.json",
        help="Fichier JSON de config (chemin relatif au dossier racine du projet)"
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(project_root, args.config)

    print(f"Chargement config depuis : {config_path}")

    cfg = load_config(config_path)

    # Récupération des infos de config
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

        print("\n--- TARE ---")
        try:
            r = bal.tare()
            print("tare ->", repr(r))
        except Exception as e:
            print("tare échoué :", e)

        time.sleep(1.0)

    finally:
        print("\nFermeture du port série")
        bal.close()


if __name__ == "__main__":
    main()
