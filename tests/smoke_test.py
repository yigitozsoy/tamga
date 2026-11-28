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

# winget tablosu (İngilizce ve Türkçe başlık, dönen çubuk, ikinci tablo)
from tamga import winget as W  # noqa: E402
WG_EN = ("   - \r   \\ \r\r"
         "Name                       Id                Version       Available     Source\r\n"
         "--------------------------------------------------------------------------------\r\n"
         "Discord                    Discord.Discord   1.0.9200      1.0.9210      winget\r\n"
         "Zoom Workplace             Zoom.Zoom.EXE     7.1.9 (48550) 7.2.5 (51704) winget\r\n"
         "2 upgrades available.\r\n\r\n"
         "The following packages have an upgrade available, but require explicit targeting for upgrade:\r\n"
         "Name   Id        Version Available Source\r\n"
         "-----------------------------------------\r\n"
         "Pinned Pin.Ned   1.0     2.0       winget\r\n")
r = W.parse_upgrades(WG_EN)
check("winget: tablo okunur", [x["id"] for x in r] == ["Discord.Discord", "Zoom.Zoom.EXE"]
      and r[1]["version"] == "7.1.9 (48550)" and r[1]["available"] == "7.2.5 (51704)" and r[0]["name"] == "Discord")
WG_TR = ("Ad            Kimlik            Sürüm    Kullanılabilir Kaynak\n"
         "--------------------------------------------------------------\n"
         "Google Chrome Google.Chrome.EXE 131.0.1  132.0.2        winget\n")
r = W.parse_upgrades(WG_TR)
check("winget: Türkçe başlık", len(r) == 1 and r[0]["id"] == "Google.Chrome.EXE" and r[0]["available"] == "132.0.2")
check("winget: güncelleme yoksa boş", W.parse_upgrades("No installed package found matching input criteria.") == [])
SHOW = ("Installer:\n  Installer Type: wix\n  Yükleyici URL'si: https://example.org/x/vlc-3.0.24-win64.msi\n"
        "  Installer SHA256: 22172095ce4c2d5f5b600bb4c142d78105db29a77fa59a931941876f3b20f6d0\n")
check("winget show: kurulum adresi (dilden bağımsız)", W.parse_installer_url(SHOW) == "https://example.org/x/vlc-3.0.24-win64.msi"
      and W.parse_installer_url("Homepage: https://a.b\n") == "")
check("önerilen: Microsoft ve güvenlik", W.recommended("Microsoft.VCRedist.2015+.x64") and W.recommended("oracle.javaruntimeenvironment")
      and not W.recommended("Valve.Steam") and not W.recommended("Discord.Discord")
      and not W.recommended("Microsoft.Teams") and not W.recommended("Microsoft.Outlook"))
check("hata nedenleri", W.reason(-1978335159) == "fail" and W.reason(-2147009240) == "admin"
      and W.reason(-1978334975) == "in_use" and W.reason(-1978334963) == "other_version" and W.reason(1223) == "denied"
      and W.ok(0) and W.ok(-1978335189) and W.ok(-1978334967) and not W.ok(1)
      and W.code_hex(-1978335159) == "0x8A150049")
check("simge: ad eşleşmesi", W.match_icon("Microsoft Visual Studio Code (User)", {"microsoft visual studio code (user)": "a"}) == "a"
      and W.match_icon("Microsoft Visual C++ v14 Redistributable", {"microsoft visual c++ v14 redistributable (x64) - 14.5": "b"}) == "b"
      and W.match_icon("Git", {"github cli": "c"}) == "")
stage = os.path.join(TMP, "WinGet")
os.makedirs(os.path.join(stage, "VideoLAN.VLC.3.0.24"))
open(os.path.join(stage, "VideoLAN.VLC.3.0.24", "DO1.tmp"), "wb").write(b"x" * 5000)
check("indirme ilerlemesi: geçici klasördeki dosya", W.staged_bytes("VideoLAN.VLC", stage) == 5000
      and W.staged_bytes("VideoLAN.VL", stage) == 0)
W.clear_staged("VideoLAN.VLC", stage)
check("eski indirme temizlenir", not os.listdir(stage))
check("sürüm notu: GitHub'ın kendi satırları atılır",
      github.clean_notes("**Full Changelog**: https://x/compare/v1...v2") == ""
      and github.clean_notes("## What's Changed\n**Full Changelog**: x") == ""
      and github.clean_notes("## yazıt 3.6\n\n- yeni şey\n\nCo-Authored-By: C <n@x>") == "## yazıt 3.6\n\n- yeni şey")

src = open(os.path.join(ROOT, "sync", "tamga_sync.py"), encoding="utf-8").read()
desk = os.path.dirname(ROOT)
for rel in (r"kamug\kamug", r"erk\erk", r"yazıt\yazit", r"mergen\mergen"):
    p = os.path.join(desk, rel, "tamga_sync.py")
    if os.path.isfile(p):
        check(f"tamga_sync eş: {rel}", open(p, encoding="utf-8").read() == src)

if "--no-gui" not in sys.argv:
    print("arayüz")
    from PyQt6.QtCore import Qt
    import threading
    from PyQt6.QtWidgets import QApplication, QLabel
    app = QApplication(sys.argv)
    fake = {
        "tamga": {"version": "9.9", "page": "p", "asset_url": "u", "asset_name": "tamga-setup-9.9.exe"},
        "kamug": {"version": "9.1", "page": "p", "asset_url": "u", "asset_name": "kamug-setup-9.1.exe"},
        "erk": {"error": "none"},
        "yazit": {"version": "3.0", "page": "p", "asset_url": "u", "asset_name": "yazit-setup-3.0.exe"},
        "bediz": {"error": "net"},
        "mergen": {"version": "0.2", "page": "p", "asset_url": "u", "asset_name": "mergen-setup-0.2.exe"},
    }
    github.latest = lambda repo: dict(fake[next((a.id for a in A.APPS if a.repo == repo), "tamga")])
    prefs.set("releases_checked", 0)
    fake["kamug"].update(notes="## kamug 9.1\n\n- yeni", size=25 * 1024 ** 2)
    wg_fake = [{"name": "Discord", "id": "Discord.Discord", "version": "1.0", "available": "1.1", "source": "winget"},
               {"name": "Steam", "id": "Valve.Steam", "version": "2.0", "available": "2.1", "source": "winget"},
               {"name": "Visual C++", "id": "Microsoft.VCRedist.2015+.x64", "version": "14.5", "available": "14.6",
                "source": "winget"}]
    W.list_upgrades = lambda: ([dict(x) for x in wg_fake], "")
    W.size = lambda pid: {"Discord.Discord": 100 * 1024 ** 2, "Valve.Steam": 0}.get(pid, 20 * 1024 ** 2)
    W.staged_bytes = lambda pid, root=None: 50 * 1024 ** 2
    wg_calls = []
    gate = threading.Event()

    admin_calls = []

    def fake_upgrade(pid, on_phase=None, admin=False, machine=False):
        (admin_calls if admin else wg_calls).append((pid, machine) if admin else pid)
        on_phase and on_phase("download")
        gate.wait(5)
        on_phase and on_phase("install")
        return 0 if pid != "Valve.Steam" else (-1978335159 if not admin else 1223)   # 0x8A150049 MSI; izin verilmedi
    W.upgrade = fake_upgrade
    W.machine_installed = lambda name: name == "Steam"
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

    # diğer uygulamalar sekmesi (winget sahte)
    w.set_tab(1)
    check("sekme 2 açılır ve hatırlanır", w.stack.currentIndex() == 1 and prefs.get("tab") == 1)
    w.check_other()
    end = time.time() + 5
    while w._wg_checking and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    def pump(cond, secs=5):
        end = time.time() + secs
        while cond() and time.time() < end:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
    pump(lambda: w._wg_sizing)
    check("winget: satırlar ve sayaç", set(w.wg_rows) == {"Discord.Discord", "Valve.Steam", "Microsoft.VCRedist.2015+.x64"}
          and "3" in w.tabs[1].text() and w.btn_all.isVisible() and "3 güncelleme" in w.wg_status.text())
    check("önerilen başta, işaretli, ayrı düğme", list(w.wg_rows)[0] == "Microsoft.VCRedist.2015+.x64"
          and w.wg_rows["Microsoft.VCRedist.2015+.x64"].findChild(QLabel, "Badge") is not None
          and w.wg_rows["Discord.Discord"].findChild(QLabel, "Badge") is None
          and w.btn_rec.isVisible() and "1 önerilen" in w.wg_status.text())
    check("boyut: satırda ve toplam", "100 MB" in w.wg_rows["Discord.Discord"].status.text()
          and "toplam ≈ 120 MB" in w.wg_status.text() and prefs.get("wg_sizes")["Discord.Discord"][1] == 100 * 1024 ** 2)
    check("kart: sürüm boyutu ve Yenilikler", "25 MB" in c["kamug"].status.text() and c["kamug"].btn_page.text() == "Yenilikler")
    c["kamug"]._page()
    check("kart: Yenilikler açılır", not c["kamug"].notes.isHidden() and "yeni" in c["kamug"].notes.text())

    # gizle / atla
    w.skip("Valve.Steam", "2.1")
    check("sürümü atla: listeden ve sayaçtan düşer", "Valve.Steam" not in w.wg_rows and "2 güncelleme" in w.wg_status.text()
          and w.btn_hidden.isVisible() and "(1)" in w.btn_hidden.text())
    w._toggle_hidden()
    check("gizlenenler gösterilir", "Valve.Steam" in w.wg_rows and "atlandı" in w.wg_rows["Valve.Steam"].status.text()
          and not w.wg_rows["Valve.Steam"].btn.isVisible() and w.wg_rows["Valve.Steam"].btn_menu.text() == "Yeniden göster")
    w.wg_rows["Valve.Steam"]._menu()
    w._toggle_hidden()
    check("yeniden göster", "Valve.Steam" in w.wg_rows and not w.btn_hidden.isVisible())

    # sıra
    w.update_all()
    pump(lambda: w.wg_jobs.get("Microsoft.VCRedist.2015+.x64", {}).get("phase") != "download")
    w._wg_tick()
    check("sıra kartı: şu an, kaçıncı, sıradakiler", w.q_card.isVisible() and "Visual C++" in w.q_title.text()
          and w.q_count.text() == "1 / 3" and "Discord" in w.q_next.text())
    check("indirme yüzdesi geçici dosyadan", w.wg_jobs["Microsoft.VCRedist.2015+.x64"]["p"] == 99
          and "İndiriliyor" in w.wg_rows["Microsoft.VCRedist.2015+.x64"].btn.text())
    check("sıradaki satır: Sırada · n", w.wg_rows["Discord.Discord"].btn.text() == "Sırada · 1"
          and w.wg_rows["Valve.Steam"].btn.text() == "Sırada · 2")
    w.dequeue("Discord.Discord")
    check("sıradan çıkar", "Discord.Discord" not in w.wg_jobs and w.q_count.text() == "1 / 2")
    gate.set()
    pump(lambda: w.wg_jobs or w._wg_worker)
    check("winget: sırayla güncellenir", wg_calls == ["Microsoft.VCRedist.2015+.x64", "Valve.Steam"])
    check("winget: başarılı satır kalkar, başarısız hata gösterir", set(w.wg_rows) == {"Discord.Discord", "Valve.Steam"}
          and "Güncellenemedi" in w.wg_rows["Valve.Steam"].status.text() and not w.q_card.isVisible()
          and "1 güncellendi, 1 güncellenemedi" in w.wg_status.text()
          and {x["id"] for x in prefs.get("wg_upgrades")} == {"Discord.Discord", "Valve.Steam"})
    steam = w.wg_rows["Valve.Steam"]
    check("başarısız: yönetici olarak dene, hata kodu ipucunda", steam.btn.text() == "Yönetici olarak dene"
          and "0x8A150049" in steam.status.toolTip() and "yönetici izni" in steam.status.text())
    steam._act()
    pump(lambda: w.wg_jobs or w._wg_worker)
    check("yönetici olarak: herkes için kurulu -> machine", admin_calls == [("Valve.Steam", True)]
          and "verilmedi" in w.wg_rows["Valve.Steam"].status.text())
    w.wg_failed["Valve.Steam"] = (-1978334975, False)      # 0x8A150101: uygulama açık
    w._fill_other()
    check("açık uygulama: kapat ve yeniden dene", "kapatıp" in w.wg_rows["Valve.Steam"].status.text()
          and w.wg_rows["Valve.Steam"].btn.text() == "Güncelle")
    w.set_tab(0)

    prefs.set("sync_apps", ["kamug"])
    w.set_shared(theme="midnight")
    d = json.load(open(kp, encoding="utf-8"))
    check("arayüzden tema: kamug'a yazıldı", d["theme"] == "midnight" and d["dark_variant"] == "midnight")
    w.set_shared(language="en")
    check("dil değişince arayüz İngilizce", w.cards["kamug"].btn_open.text() == "Open")
    w.close()

print("\n" + ("TÜM TESTLER GEÇTİ" if not fails else f"{len(fails)} HATA: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
