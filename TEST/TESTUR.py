from automated_arm import UR
from config import load_config
import time

def main():
    # Charger la configuration
    cfg = load_config()

    # Créer l'instance UR
    ur = UR(
        ip_address=cfg["ur"]["ip_address"],
        timeout_ms=cfg["ur"]["timeout_ms"],
        verbose=cfg["ur"]["verbose"]
    )

    try:
        print("Connexion au robot...")
        ur.connect()

        # Nom du programme URP de test (assure-toi qu'il existe sur ton robot)
        test_program = "louis_test.urp"
        print(f"Lancement du programme {test_program}…")
        ur.run_program(test_program)

        print("Test terminé ✅")

    except Exception as e:
        print(f"Erreur : {e}")

    finally:
        ur.disconnect()
        print("Déconnecté du robot 🔌")

if __name__ == "__main__":
    main()