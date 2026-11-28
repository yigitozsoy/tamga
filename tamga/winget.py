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
    return {k: v["icon"] for k, v in arp().items() if v["icon"]}


def machine_installed(name):
    """Uygulama herkes için mi kurulu (kaldırma kaydı HKLM'de)? Öyleyse yönetici kurulumu --scope machine ister."""
    return bool(match_icon(name, {k: 1 for k, v in arp().items() if v["machine"]}))


def arp():
    """Kurulu programlar: küçük harfli görünen ad -> {icon, machine}. Aynı ad iki yerdeyse kullanıcınınki."""
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
                if name:
                    e = out.setdefault(name.lower(), {"icon": icon, "machine": hive != winreg.HKEY_CURRENT_USER})
                    e["icon"] = e["icon"] or icon
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

DENIED = 1223                     # ERROR_CANCELLED: Windows'un yönetici izni penceresinde "Hayır"
NO_APPLICABLE = 0x8A150010        # --scope machine'e uyan kurulum dosyası yok
_OK = {0, 0x8A15002B, 0x8A150109}  # başarılı / uygulanabilir güncelleme yok / yeniden başlatınca tamamlanır
_REASONS = {
    0x8A150101: "in_use", 0x8A150103: "in_use", 0x8A150111: "in_use",
    0x8A15010D: "other_version", 0x8A15010A: "reboot", 0x8A150107: "network", 0x8A150105: "disk",
    0x80073D28: "admin", DENIED: "denied",
}


def ok(code):
    return (code & 0xFFFFFFFF) in _OK


def reason(code):
    """Çıkış kodu -> in_use | other_version | reboot | network | disk | admin | denied | fail.

    "fail" çoğunlukla yönetici izni eksikliğidir: herkes için kurulu MSI'ı sessiz (izin penceresiz) kurulum
    güncelleyemez (1603), eski sürümü kaldıramaz…"""
    return _REASONS.get(code & 0xFFFFFFFF, "fail")


def code_hex(code):
    return f"0x{code & 0xFFFFFFFF:08X}"


def _signed(c):
    return c - (1 << 32) if c >= (1 << 31) else c


def run_elevated(file, params):
    """Yönetici olarak (Windows izin sorar), gizli pencerede çalıştır. -> (süreç tutamacı, 0) | (None, hata)."""
    import ctypes
    from ctypes import wintypes

    class SEI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    sei = SEI(cbSize=ctypes.sizeof(SEI), fMask=0x40 | 0x100,      # NOCLOSEPROCESS | NOASYNC
              lpVerb="runas", lpFile=file, lpParameters=params, nShow=0)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    if not shell32.ShellExecuteExW(ctypes.byref(sei)) or not sei.hProcess:
        return None, ctypes.get_last_error() or DENIED
    return sei.hProcess, 0


def run_elevated_ps(script):
    """PowerShell betiğini yönetici olarak, gizli çalıştır. -> (tutamaç, 0) | (None, hata)."""
    import base64
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    return run_elevated("powershell.exe", f"-NoProfile -NonInteractive -ExecutionPolicy Bypass "
                                          f"-WindowStyle Hidden -EncodedCommand {enc}")


def proc_running(h):
    import ctypes
    return bool(h) and ctypes.windll.kernel32.WaitForSingleObject(h, 0) == 0x102     # WAIT_TIMEOUT


def proc_close(h):
    import ctypes
    if h:
        ctypes.windll.kernel32.CloseHandle(h)


def ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def write_json(path, obj):
    """Yarım dosya okunmasın: geçici dosyaya yaz, sonra yerine taşı."""
    import json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def read_json(path):
    import json
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# Yönetici çalıştırıcısı: izin bir kez sorulur, sıradaki tüm paketler aynı yönetici PowerShell'inde kurulur.
# tamga job.json'a {seq, id, machine} yazar; çalıştırıcı winget'i çalıştırıp result.json'a {seq, code} yazar.
# tamga kapanırsa (üst süreç yok) ya da {quit} gelirse çıkar.
_RUNNER = r"""
$dir = {dir}; $parent = {parent}; $w = {winget}; $seq = 0
$job = Join-Path $dir 'job.json'; $res = Join-Path $dir 'result.json'
while ($true) {{
  if (-not (Get-Process -Id $parent -ErrorAction SilentlyContinue) -or -not (Test-Path -LiteralPath $dir)) {{ break }}
  if (Test-Path -LiteralPath $job) {{
    $j = $null
    try {{ $j = Get-Content -LiteralPath $job -Raw -Encoding UTF8 | ConvertFrom-Json }} catch {{ }}
    if ($j -and $j.quit) {{ break }}
    if ($j -and $j.seq -gt $seq) {{
      $seq = $j.seq
      $a = @('upgrade', '--id', $j.id, '--exact', '--silent', '--include-unknown', '--accept-package-agreements',
             '--accept-source-agreements', '--disable-interactivity')
      if ($j.machine) {{
        & $w @a --scope machine | Out-Null
        if ($LASTEXITCODE -eq {no_app}) {{ & $w @a | Out-Null }}
      }} else {{ & $w @a | Out-Null }}
      $o = @{{ seq = $seq; code = $LASTEXITCODE }} | ConvertTo-Json -Compress
      [IO.File]::WriteAllText("$res.tmp", $o)
      Move-Item -LiteralPath "$res.tmp" -Destination $res -Force
    }}
  }}
  Start-Sleep -Milliseconds 300
}}
Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
"""


class AdminRunner:
    """Yönetici olarak güncelleme: ilk pakette izin sorulur, close()'a kadar aynı süreç kullanılır.

    Çıktı okunamaz: indirme winget'in geçici klasöründeki dosyadan izlenir, dosya 3 sn büyümezse kurulum.
    Herkes için kurulu uygulamada önce --scope machine (kullanıcı kurulumu "zaten herkes için kurulu" diye
    reddedilir), uygun kurulum dosyası yoksa kapsamsız yeniden."""

    def __init__(self):
        self.h = None
        self.dir = ""
        self.seq = 0

    def _start(self):
        w = exe()
        if not w:
            return -1
        self.dir = tempfile.mkdtemp(prefix="tamga-admin-")
        self.seq = 0
        script = _RUNNER.format(dir=ps_quote(self.dir), parent=os.getpid(), winget=ps_quote(w),
                                no_app=_signed(NO_APPLICABLE))
        self.h, err = run_elevated_ps(script)
        return err

    def run(self, pid, machine=False, on_phase=None):
        import time
        if not proc_running(self.h):
            self.close()
            err = self._start()
            if err:
                return err
        self.seq += 1
        res = os.path.join(self.dir, "result.json")
        clear_staged(pid)
        write_json(os.path.join(self.dir, "job.json"), {"seq": self.seq, "id": pid, "machine": bool(machine)})
        on_phase and on_phase("download")
        last, still, phase = -1, 0, "download"
        while True:
            r = read_json(res)
            if isinstance(r, dict) and r.get("seq") == self.seq:
                return int(r.get("code") or 0)
            if not proc_running(self.h):
                return -1
            time.sleep(0.5)
            if phase == "download":
                got = staged_bytes(pid)
                still = still + 1 if got and got == last else 0
                last = got
                if still >= 6:
                    phase = "install"
                    on_phase and on_phase(phase)

    def close(self):
        if self.h:
            if self.dir and proc_running(self.h):
                try:
                    write_json(os.path.join(self.dir, "job.json"), {"quit": True})
                except OSError:
                    pass
            proc_close(self.h)          # klasörü çalıştırıcı siler (çıkarken)
        self.h = None
        self.dir = ""


def upgrade(pid, on_phase=None):
    """Tek paketi sessizce güncelle. on_phase("download" | "install") aşama değişince. -> çıkış kodu.

    Çıktıda adres geçen satır ("Downloading https://…") indirmenin, ondan sonraki ilk satır
    (kurulum dosyası doğrulandı) kurulumun başladığını gösterir. Yönetici olarak: AdminRunner."""
    w = exe()
    if not w:
        return -1
    clear_staged(pid)
    args = [w, "upgrade", "--id", pid, "--exact", "--silent", "--include-unknown", "--accept-package-agreements"] + AGREE
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
