"""tamga uçtan uca testi. Gerçek tercihlere, kayıt defterine ve ağa dokunmaz; ekranda pencere açmaz.

Kullanım: python tests/smoke_test.py [--no-gui]"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="tamga_test_")
os.environ["LOCALAPPDATA"] = TMP
os.environ["APPDATA"] = os.path.join(TMP, "roaming")
os.environ["TAMGA_DATA_DIR"] = os.path.join(TMP, "tamga")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tamga  # noqa: E402
from tamga import apps as A, github, shared  # noqa: E402
from tamga.config import prefs  # noqa: E402

fails = []
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def check(name, cond):
    print(("  ok   " if cond else "  HATA ") + name)
    if not cond:
        fails.append(name)


print("çekirdek")
check("sürüm karşılaştırma", A.is_newer("3.0.0", "1.4.0") and not A.is_newer("3.0.1", "3.0.1")
      and A.is_newer("v2.10", "2.9.9") and not A.is_newer("", "1.0"))
assets = [{"name": n, "browser_download_url": n} for n in (
    "beta-1.0.0-windows-arm64.exe", "beta-1.0.0-windows-x64.exe.sha256", "appcast.xml",
    "beta-1.0.0-windows-x64.exe", "rainmeter-source.zip")]
check("kurulum dosyası seçimi (x64, arm64 değil)", github.pick_asset(assets)["name"] == "beta-1.0.0-windows-x64.exe")
check("kurulum dosyası seçimi (setup, portable değil)", github.pick_asset(
    [{"name": "kamug-portable-3.0.1.zip"}, {"name": "kamug-setup-3.0.1.exe"}])["name"] == "kamug-setup-3.0.1.exe")
check("seçilecek dosya yoksa None", github.pick_asset([{"name": "notes.txt"}]) is None)

# kurulu algılama: kaldırma kaydı yokmuş gibi, varsayılan klasördeki exe
A._reg_values = lambda guid: {}
os.makedirs(os.path.join(TMP, "Programs", "kamug"))
open(os.path.join(TMP, "Programs", "kamug", "kamug.exe"), "wb").close()
check("kurulu: exe bulunur", A.installed(A.BY_ID["kamug"]) is not None)
check("kurulu değil", A.installed(A.BY_ID["erk"]) is None)
check("çalışan süreçler okunur", os.path.normcase(sys.executable) in A.running_exes())

# ortak ayarlar
n = shared.normalize({"theme": "dark", "accent": "purple", "language": "xx"})
check("normalize", n["theme"] == "amoled" and n["accent"] == "gray" and n["language"] == "tr"
      and n["dark_variant"] == "amoled" and n["light_variant"] == "white")
kp = os.path.join(TMP, "kamug", "preferences.json")
os.makedirs(os.path.dirname(kp))
with open(kp, "w", encoding="utf-8") as f:
    json.dump({"theme": "dark_gray", "accent": "blue", "language": "en", "volume": 40}, f)
shared.seed()
check("ilk açılışta kamug'dan alınır", prefs.get("theme") == "dark_gray" and prefs.get("accent") == "blue"
      and prefs.get("language") == "en")
prefs.update(shared.normalize({"theme": "cream", "accent": "teal", "language": "tr"}))
check("uygulamaya yazılır", shared.apply_to(A.BY_ID["kamug"]) == "ok")
d = json.load(open(kp, encoding="utf-8"))
check("ortak anahtarlar + diğerleri korunur", d["theme"] == "cream" and d["light_variant"] == "cream"
      and d["accent"] == "teal" and d["language"] == "tr" and d["volume"] == 40)
check("ikinci kez: değişiklik yok", shared.apply_to(A.BY_ID["kamug"]) == "same")
check("tercih klasörü yoksa yazılmaz", shared.apply_to(A.BY_ID["erk"]) == "missing"
      and not os.path.exists(os.path.join(TMP, "erk")))
bp = os.path.join(TMP, "roaming", "bediz", "settings.json")
os.makedirs(os.path.dirname(bp))
with open(bp, "w", encoding="utf-8") as f:
    json.dump({"printers": [], "betaMonitorTheme": "amoled"}, f)
check("bediz açıkken yazılmaz", shared.apply_to(A.BY_ID["bediz"], running=True) == "running")
check("bediz kapalıyken kendi anahtarlarına yazılır", shared.apply_to(A.BY_ID["bediz"]) == "ok")
d = json.load(open(bp, encoding="utf-8"))
check("bediz: tema + vurgu, dil / çeşit anahtarı yok, diğerleri korunur", d["betaMonitorTheme"] == "cream"
      and d["betaMonitorAccent"] == "teal" and "theme" not in d and "language" not in d and d["printers"] == [])

src = open(os.path.join(ROOT, "sync", "tamga_sync.py"), encoding="utf-8").read()
desk = os.path.dirname(ROOT)
for rel in (r"kamug\kamug", r"erk\erk", r"yazıt\yazit"):
    p = os.path.join(desk, rel, "tamga_sync.py")
    if os.path.isfile(p):
        check(f"tamga_sync eş: {rel}", open(p, encoding="utf-8").read() == src)

if "--no-gui" not in sys.argv:
    print("arayüz")
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    fake = {
        "tamga": {"version": "9.9", "page": "p", "asset_url": "u", "asset_name": "tamga-setup-9.9.exe"},
        "kamug": {"version": "9.1", "page": "p", "asset_url": "u", "asset_name": "kamug-setup-9.1.exe"},
        "erk": {"error": "none"},
        "yazit": {"version": "3.0", "page": "p", "asset_url": "u", "asset_name": "yazit-setup-3.0.exe"},
        "bediz": {"error": "net"},
    }
    github.latest = lambda repo: dict(fake[next((a.id for a in A.APPS if a.repo == repo), "tamga")])
    prefs.set("releases_checked", 0)
    from tamga.window import MainWindow
    w = MainWindow()
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    w.show()
    w.check_updates(force=True)
    import time
    end = time.time() + 5
    while w._checking and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    c = w.cards
    check("kamug: güncelle düğmesi", c["kamug"].btn_act.isVisible() and c["kamug"].btn_act.text() == "Güncelle")
    check("kamug: yeni sürüm yazısı", "9.1" in c["kamug"].status.text())
    check("tamga: kendi sürümü ve güncelle düğmesi", w.lbl_ver.text().startswith(tamga.__version__)
          and "9.9" in w.lbl_ver.text() and w.btn_self.isVisible())
    check("sürümler iki parça", A.short("3.1.0") == "3.1" and A.short("2.1.1") == "2.1.1"
          and not A.is_newer("1.1", "1.1.0"))
    check("yazıt: kur düğmesi", c["yazit"].btn_act.isVisible() and c["yazit"].btn_act.text() == "Kur"
          and not c["yazit"].btn_open.isVisible())
    check("erk: yayın yok", "yayın yok" in c["erk"].status.text() and not c["erk"].btn_act.isVisible())
    check("sürüm bilgisi önbelleğe yazılır", prefs.get("releases", {}).get("kamug", {}).get("version") == "9.1")

    # kurulum bitişi (sahte süreç)
    class P:
        def poll(self):
            return 0
    fakefile = os.path.join(TMP, "x.exe")
    open(fakefile, "wb").close()
    w.jobs["kamug"] = {"phase": "install", "p": 1000}
    w._procs["kamug"] = (P(), fakefile)
    w._check_installers()
    check("kurulum bitince iş temizlenir, dosya silinir", "kamug" not in w.jobs and not os.path.exists(fakefile))

    prefs.set("sync_apps", ["kamug"])
    w.set_shared(theme="midnight")
    d = json.load(open(kp, encoding="utf-8"))
    check("arayüzden tema: kamug'a yazıldı", d["theme"] == "midnight" and d["dark_variant"] == "midnight")
    w.set_shared(language="en")
    check("dil değişince arayüz İngilizce", w.cards["kamug"].btn_open.text() == "Open")
    w.close()

print("\n" + ("TÜM TESTLER GEÇTİ" if not fails else f"{len(fails)} HATA: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
