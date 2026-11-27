"""Diğer uygulamaların güncellemeleri: Windows'un kendi paket yöneticisi winget.

`winget upgrade` tablosu okunur (sütun başlıkları dile göre değişir, bu yüzden adlarla değil konumlarla);
güncelleme `winget upgrade --id <kimlik> --exact --silent` ile, sırayla yapılır.

winget çıktısı yönlendirilince ilerleme çubuğu yazmaz: indirme ilerlemesi winget'in geçici klasöründeki
(%TEMP%\\WinGet\\<kimlik>.<sürüm>) dosyanın boyutundan, kurulum dosyasının boyutu `winget show`'daki
adresin HEAD isteğinden okunur."""
import glob
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request

from . import __version__

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
STORE_UPDATES = "ms-windows-store://downloadsandupdates"
WINGET_STORE = "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1"     # Uygulama Yükleyici (winget)
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
AGREE = ["--accept-source-agreements", "--disable-interactivity"]


# Önerilen güncellemeler: Microsoft'un bileşenleri (çalışma ortamları, Visual C++, Office, Teams…) ve
# internete açık / güvenlik açığı sık çıkan yaygın programlar. Kimliğin başı eşleşir (büyük-küçük harf önemsiz).
RECOMMENDED = (
    "Microsoft.", "Google.Chrome", "Mozilla.Firefox", "Brave.Brave", "Opera.Opera", "Oracle.JavaRuntimeEnvironment",
    "Oracle.JDK", "EclipseAdoptium.", "Git.Git", "OpenJS.NodeJS", "Python.Python.", "7zip.7zip", "RARLab.WinRAR",
    "Adobe.Acrobat.Reader", "Zoom.Zoom", "VideoLAN.VLC", "Notepad++.Notepad++", "PuTTY.PuTTY", "WinSCP.WinSCP",
    "KeePassXCTeam.KeePassXC", "Bitwarden.Bitwarden", "AnyDesk.AnyDesk", "TeamViewer.TeamViewer",
)


# Microsoft'un olup önerilmeyenler: bileşen değil, kendi kendini güncelleyen uygulamalar
NOT_RECOMMENDED = ("Microsoft.Teams", "Microsoft.Outlook")


def recommended(pid):
    p = (pid or "").lower()
    if any(p.startswith(r.lower()) for r in NOT_RECOMMENDED):
        return False
    return any(p.startswith(r.lower()) for r in RECOMMENDED)


def exe():
    return shutil.which("winget")


def _clean(text):
    """Dönen çubuk / ilerleme satırlarını at: her satırın son \\r'den sonrası kalır."""
    return [ln.rsplit("\r", 1)[-1].rstrip() for ln in text.replace("\r\n", "\n").split("\n")]


def parse_upgrades(text):
    """`winget upgrade` çıktısı -> [{name, id, version, available, source}].

    Başlık satırı (Name Id Version Available Source, ya da Türkçesi) tire satırının hemen üstündedir;
    sütun başlangıçları başlıktaki sözcüklerin konumu. Tablo ilk boş satırda biter (altındaki
    "açık hedefleme gerektirenler" tablosu alınmaz)."""
    lines = _clean(text)
    out = []
    for i, ln in enumerate(lines):
        if i == 0 or not re.fullmatch(r"-{10,}", ln.strip()):
            continue
        head = lines[i - 1]
        cols = [m.start() for m in re.finditer(r"\S+", head)]
        if len(cols) < 4:
            continue
        for row in lines[i + 1:]:
            if not row.strip():
                break
            cells = [row[a:b].strip() for a, b in zip(cols, cols[1:] + [None])]
            pid = cells[1]
            if not pid or " " in pid:
                continue
            out.append({"name": cells[0].rstrip("…").strip() or pid, "id": pid, "version": cells[2],
                        "available": cells[3], "source": cells[4] if len(cells) > 4 else ""})
        break
    return out


def list_upgrades():
    """-> (liste, hata). hata: "" | "missing" | "fail". Her satıra kurulu uygulamanın simgesi ("icon") eklenir."""
    w = exe()
    if not w:
        return [], "missing"
    try:
        p = subprocess.run([w, "upgrade", "--include-unknown"] + AGREE,
                           capture_output=True, timeout=180, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return [], "fail"
    rows = parse_upgrades(p.stdout.decode("utf-8", "replace"))
    icons = arp_icons()
    for r in rows:
        r["icon"] = match_icon(r["name"], icons)
    return rows, ("" if rows or p.returncode in (0, -1978335212) else "fail")   # 0x8A150014: güncelleme yok


# --- simgeler: kaldırma kayıtlarındaki DisplayIcon --------------------------------

def _icon_path(v):
    """'"C:\\x\\app.exe",0' -> C:\\x\\app.exe (yoksa "")."""
    v = (v or "").strip()
    m = re.fullmatch(r'"?(.+?)"?\s*(?:,\s*-?\d+)?', v)
    path = os.path.expandvars(m.group(1).strip().strip('"')) if m else ""
    return path if path and os.path.isfile(path) else ""


def _exe_in(folder, name):
    """DisplayIcon yoksa kurulum klasöründeki asıl exe: adı uygulamanın adına en çok benzeyen, kaldırıcı değil."""
    folder = os.path.expandvars((folder or "").strip().strip('"'))
    if not folder or not os.path.isdir(folder):
        return ""
    words = set(re.findall(r"[a-z]{3,}", name.lower()))
    best, score = "", -1
    try:
        for f in os.scandir(folder):
            n = f.name.lower()
            if not n.endswith(".exe") or re.search(r"unins|uninst|setup|update|crash|helper", n):
                continue
            s = sum(w in n for w in words)
            if s > score:
                best, score = f.path, s
    except OSError:
        return ""
    return best


def arp_icons():
    """Kurulu programlar: küçük harfli görünen ad -> simge dosyası."""
    out = {}
    try:
        import winreg
    except ImportError:
        return out
    views = ((winreg.HKEY_CURRENT_USER, 0), (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
             (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY))
    for hive, view in views:
        try:
            root = winreg.OpenKey(hive, UNINSTALL, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        name = str(winreg.QueryValueEx(k, "DisplayName")[0]).strip()
                        icon = ""
                        try:
                            icon = _icon_path(str(winreg.QueryValueEx(k, "DisplayIcon")[0]))
                        except OSError:
                            pass
                        if not icon:
                            try:
                                icon = _exe_in(str(winreg.QueryValueEx(k, "InstallLocation")[0]), name)
                            except OSError:
                                pass
                except OSError:
                    continue
                if name and icon:
                    out.setdefault(name.lower(), icon)
    return out


def match_icon(name, icons):
    """winget'in adı kaldırma kaydındaki ad (uzunsa kırpılmış): önce tam, sonra baş eşleşmesi."""
    n = (name or "").lower().strip()
    if not n:
        return ""
    if n in icons:
        return icons[n]
    for k, v in icons.items():
        if len(n) >= 6 and (k.startswith(n) or n.startswith(k)):
            return v
    return ""


# --- kurulum dosyasının boyutu ----------------------------------------------------

def parse_installer_url(text):
    """`winget show` çıktısında kurulum adresi: SHA256 satırının hemen üstündeki adres (dilden bağımsız)."""
    lines = _clean(text)
    for i, ln in enumerate(lines):
        if re.search(r"\b[0-9a-fA-F]{64}\b", ln):
            for back in lines[max(0, i - 3):i][::-1]:
                m = re.search(r"https?://\S+", back)
                if m:
                    return m.group(0)
    return ""


def url_size(url, timeout=15):
    """Uzunluk başlığından bayt (bilinmiyorsa 0)."""
    hdr = {"User-Agent": f"tamga/{__version__}"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr, method="HEAD"), timeout=timeout) as r:
            n = int(r.headers.get("Content-Length") or 0)
            if n > 1024:
                return n
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers=dict(hdr, Range="bytes=0-0"))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            m = re.search(r"/(\d+)", r.headers.get("Content-Range") or "")
            return int(m.group(1)) if m else 0
    except Exception:
        return 0


def size(pid):
    """Paketin son sürümünün kurulum dosyası boyutu (bayt, bilinmiyorsa 0)."""
    w = exe()
    if not w:
        return 0
    try:
        p = subprocess.run([w, "show", "--id", pid, "--exact"] + AGREE,
                           capture_output=True, timeout=60, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    url = parse_installer_url(p.stdout.decode("utf-8", "replace"))
    return url_size(url) if url else 0


def staged_bytes(pid, root=None):
    """winget'in o paket için indirdiği bayt (%TEMP%\\WinGet\\<kimlik>.<sürüm>\\ içindeki en büyük dosya)."""
    root = root or os.path.join(tempfile.gettempdir(), "WinGet")
    best = 0
    for d in glob.glob(os.path.join(glob.escape(root), glob.escape(pid) + ".*")):
        try:
            for f in os.scandir(d):
                if f.is_file():
                    best = max(best, os.stat(f.path).st_size)   # dizin kaydı yazarken güncellenmez: stat
        except OSError:
            pass
    return best


def clear_staged(pid, root=None):
    """Önceki denemeden kalan dosya yeni indirmenin ilerlemesini şaşırtmasın."""
    root = root or os.path.join(tempfile.gettempdir(), "WinGet")
    for d in glob.glob(os.path.join(glob.escape(root), glob.escape(pid) + ".*")):
        shutil.rmtree(d, ignore_errors=True)


# --- güncelleme -------------------------------------------------------------------

def upgrade(pid, on_phase=None):
    """Tek paketi sessizce güncelle. on_phase("download" | "install") aşama değişince. -> çıkış kodu.

    Çıktıda adres geçen satır ("Downloading https://…") indirmenin, ondan sonraki ilk satır
    (kurulum dosyası doğrulandı) kurulumun başladığını gösterir."""
    w = exe()
    if not w:
        return -1
    args = [w, "upgrade", "--id", pid, "--exact", "--silent", "--include-unknown",
            "--accept-package-agreements"] + AGREE
    clear_staged(pid)
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError:
        return -1
    phase = ""
    for raw in p.stdout:
        ln = raw.decode("utf-8", "replace").rstrip("\r\n").rsplit("\r", 1)[-1].strip()
        if not ln:
            continue
        nxt = phase
        if "://" in ln and not phase:
            nxt = "download"
        elif phase == "download":
            nxt = "install"
        if nxt != phase:
            phase = nxt
            on_phase and on_phase(phase)
    return p.wait()
