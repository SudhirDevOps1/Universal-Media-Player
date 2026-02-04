import json
import os

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "last_media_path": "",
    "last_position": 0,
    "volume": 70,
    "last_playlist": []
}

def load_settings():
    """Loads settings from a JSON file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Saves settings to a JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")
