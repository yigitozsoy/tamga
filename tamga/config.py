"""Yollar ve tamga'nın kendi tercihleri (%LOCALAPPDATA%\\tamga\\preferences.json)."""
import json
import os
import sys
import threading

LOCAL = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
ROAMING = os.environ.get("APPDATA", os.path.expanduser("~"))
# TAMGA_DATA_DIR: testler tamga'nın kendi verisini geçici klasöre yönlendirir
DATA_DIR = os.environ.get("TAMGA_DATA_DIR") or os.path.join(LOCAL, "tamga")
PREFS_FILE = os.path.join(DATA_DIR, "preferences.json")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")

if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def asset(*parts):
    return os.path.join(BASE_DIR, "assets", *parts)


DEFAULTS = {
    # Ortak ayarlar: ilk açılışta ailenin mevcut tercihlerinden doldurulur (shared.seed)
    "language": "tr",
    "theme": "amoled",
    "dark_variant": "amoled",
    "light_variant": "white",
    "accent": "gray",
    "sync_apps": ["kamug", "erk", "yazit", "bediz"],
    "seeded": False,
    "releases": {},          # uygulama -> son GitHub sürüm bilgisi (önbellek)
    "releases_checked": 0,
    "window_geometry": None,
}


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path, data, indent=1):
    """Yarım dosya kalmasın: geçici dosyaya yazıp yerine koyar."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tamga.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


class Prefs:
    def __init__(self, path=PREFS_FILE):
        self.path = path
        self.data = dict(DEFAULTS)
        self._lock = threading.Lock()
        self.data.update(read_json(path) or {})

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return DEFAULTS.get(key, default)

    def set(self, key, value):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self.save()

    def update(self, values):
        self.data.update(values)
        self.save()

    def save(self):
        with self._lock:
            try:
                write_json(self.path, self.data)
            except OSError:
                pass


prefs = Prefs()
