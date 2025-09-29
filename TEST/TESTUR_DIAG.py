from automated_arm import UR
from config import load_config
import time
import socket

def test_dashboard_server(ip: str, port: int = 29999, timeout: float = 5.0):
    """Test rapide si le port Dashboard est accessible"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.close()
        return True
    except Exception as e:
        return False

def main():
    cfg = load_config()
    ip = cfg["ur"]["ip_address"]

    print(f"🔍 Vérification du port Dashboard server {ip}:29999…")
    if not test_dashboard_server(ip):
        print("❌ Le port 29999 n'est pas accessible. Vérifie l'IP, le réseau et le firewall.")
        return
    print("✅ Port accessible, tentative de connexion via dashboard_client…")

    ur = UR(ip_address=ip, timeout_ms=15000, verbose=True)

    for attempt in range(1, 4):
        try:
            print(f"Connexion au robot… (essai {attempt}/3)")
            ur.connect()
            print("✅ Connexion réussie !")
            ur.disconnect()
            return
        except Exception as e:
            print(f"⚠ Échec de connexion : {e}")
            time.sleep(2)

    print("❌ Impossible de se connecter après 3 essais. Vérifie le Dashboard server et le réseau.")

if __name__ == "__main__":
    main()
