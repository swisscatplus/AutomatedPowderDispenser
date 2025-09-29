import json
import os

def load_config(path: str = None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "settings.json")
    with open(path, "r") as f:
        return json.load(f)