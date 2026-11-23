"""Ailenin uygulamaları: kurulum kaydı, GitHub deposu, tercih dosyası.

AppId'ler her uygulamanın Inno Setup betiğindeki değerlerdir (kaldırma kaydı: HKCU\\...\\Uninstall\\{AppId}_is1)."""
import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass, field

from .config import LOCAL, ROAMING

PROGRAMS = os.path.join(LOCAL, "Programs")
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


@dataclass
class App:
    id: str
    name: str
    desc: tuple            # (tr, en)
    repo: str
    app_guid: str
    folder: str
    exe: str
    prefs: list = field(default_factory=list)   # tercih dosyası adayları (ilk var olan kullanılır)
    shares_theme: bool = True
    key_map: dict = field(default_factory=dict)   # ortak anahtar -> uygulamadaki ad (boşsa aynı adlar)
    live: bool = True      # açıkken dosyadaki değişikliği kendisi uygular (tamga_sync); değilse kapalıyken yazılır
    indent: int = 1

    @property
    def logo(self):
        from .config import asset
        return asset("apps", self.id + ".png")


APPS = [
    App("kamug", "kamug", ("Medya oynatıcı", "Media player"), "yigitozsoy/kamug_oynatici",
        "{6F1C2B8E-4A7D-4E2B-9C61-0A9D3E5B7C21}", "kamug", "kamug.exe",
        [os.path.join(LOCAL, "kamug", "preferences.json"), os.path.join(LOCAL, "gamma", "preferences.json")]),
    App("erk", "erk", ("Planlayıcı", "Planner"), "yigitozsoy/erk_planlayici",
        "{F860D8FB-6391-4191-A455-E7B16CC98124}", "erk", "erk.exe",
        [os.path.join(LOCAL, "erk", "preferences.json")]),
    App("yazit", "yazıt", ("Not, ekran kaydı, çizim", "Notes, screen recording, drawing"), "yigitozsoy/yazit_tahta",
        "{274E63FA-2C5A-402B-BC02-3F663C51EDA8}", "yazit", "yazit.exe",
        [os.path.join(LOCAL, "yazit", "preferences.json")]),
    App("bediz", "bediz", ("Bambu Lab yazıcı takibi", "Bambu Lab printer monitor"), "yigitozsoy/bediz_takip",
        "{40AB2714-4329-4530-81BD-5ECDC7D268D0}", "bediz", "bediz.exe",
        [os.path.join(ROAMING, "bediz", "settings.json")],
        # bediz (.NET) aynı tema çeşitlerini ve vurguları kullanır, anahtar adları eski addan kalma; dil ayarı yok
        key_map={"theme": "betaMonitorTheme", "accent": "betaMonitorAccent"}, live=False, indent=2),
]
BY_ID = {a.id: a for a in APPS}


@dataclass
class Installed:
    version: str
    exe: str
    location: str
    uninstall: str = ""


def parse_version(s):
    nums = [int(x) for x in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def short(v):
    """Ailenin sürüm biçimi: iki parça ("3.1.0" -> "3.1"); sıfır olmayan üçüncü parça kalır."""
    nums = [int(x) for x in re.findall(r"\d+", v or "")[:3]]
    if not nums:
        return v or ""
    while len(nums) > 2 and nums[-1] == 0:
        nums.pop()
    return ".".join(map(str, nums + [0] * (2 - len(nums))))


def is_newer(remote, local):
    return bool(remote) and parse_version(remote) > parse_version(local)


def _reg_values(guid):
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, UNINSTALL + "\\" + guid + "_is1") as k:
                out = {}
                for name in ("DisplayVersion", "InstallLocation", "DisplayIcon", "UninstallString"):
                    try:
                        out[name] = str(winreg.QueryValueEx(k, name)[0])
                    except OSError:
                        pass
                return out
        except OSError:
            continue
    return {}


def file_version(path):
    """exe'nin sürüm kaynağından "1.2" / "1.2.3" (yoksa "")."""
    try:
        ver = ctypes.WinDLL("version")
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return ""
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return ""
        p = ctypes.c_void_p()
        n = wintypes.UINT()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(n)):
            return ""

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [(f, wintypes.DWORD) for f in (
                "sig", "struc", "fvms", "fvls", "pvms", "pvls", "mask", "flags", "os", "type", "sub", "dms", "dls")]
        fi = ctypes.cast(p, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        return short(f"{fi.pvms >> 16}.{fi.pvms & 0xFFFF}.{fi.pvls >> 16}")
    except Exception:
        return ""


def installed(app):
    """Kurulu mu, hangi sürüm? Önce kaldırma kaydı, yoksa / exe yoksa varsayılan klasör ve exe sürümü."""
    reg = _reg_values(app.app_guid)
    loc = reg.get("InstallLocation", "").strip().strip('"')
    exe = os.path.join(loc, app.exe) if loc else ""
    if not exe or not os.path.isfile(exe):
        exe = os.path.join(PROGRAMS, app.folder, app.exe)
        if not os.path.isfile(exe):
            return None
        reg = {}                       # kayıt başka bir yeri gösteriyordu: güvenme
    version = short(reg.get("DisplayVersion") or file_version(exe))
    return Installed(version=version, exe=exe, location=os.path.dirname(exe),
                     uninstall=reg.get("UninstallString", ""))


# --- çalışan süreçler -------------------------------------------------------

def running_exes():
    """Açık süreçlerin exe yolları (küçük harf, normcase)."""
    out = set()
    try:
        psapi = ctypes.WinDLL("psapi")
        k32 = ctypes.WinDLL("kernel32")
        arr = (wintypes.DWORD * 4096)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
            return out
        k32.OpenProcess.restype = wintypes.HANDLE
        for pid in arr[:needed.value // ctypes.sizeof(wintypes.DWORD)]:
            h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                continue
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    out.add(os.path.normcase(buf.value))
            finally:
                k32.CloseHandle(wintypes.HANDLE(h))
    except Exception:
        pass
    return out


def is_running(inst, exes=None):
    if not inst:
        return False
    exes = running_exes() if exes is None else exes
    return os.path.normcase(inst.exe) in exes
