# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tanımı. packaging\build.ps1 üzerinden çalıştırın.
# Çıktı: build\dist\tamga\tamga.exe
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(ROOT, "tamga", "assets"), "assets")]
hiddenimports = ["PyQt6.QtNetwork"]

EXCLUDES = [
    "tkinter", "unittest", "pydoc", "test", "lib2to3", "matplotlib", "scipy", "pandas", "numpy", "IPython",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebChannel", "PyQt6.QtQml",
    "PyQt6.QtQuick", "PyQt6.QtQuickWidgets", "PyQt6.Qt3DCore", "PyQt6.QtBluetooth", "PyQt6.QtSql",
    "PyQt6.QtTest", "PyQt6.QtDesigner", "PyQt6.QtHelp", "PyQt6.QtPdf", "PyQt6.QtPdfWidgets",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtPositioning", "PyQt6.QtSensors",
    "PyQt6.QtSerialPort", "PyQt6.QtCharts", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "PyQt6.QtSvg", "PIL",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)
# --- paketi hafiflet: kullanılmayan Qt / DLL dosyaları (~30 MB) -----------------------------------------
# opengl32sw: yazılımsal OpenGL (uygulama OpenGL kullanmıyor) · Qt çevirileri: yalnızca tr / en
# görüntü biçimleri: gif / ico / jpeg / svg / webp kalır · platform: yalnızca qwindows
# TLS: GitHub istekleri Python urllib ile → Qt'nin OpenSSL arka ucu ve onun libssl/libcrypto-3-x64 kopyası gereksiz
# (Python'un _ssl / _hashlib'i libssl-3.dll / libcrypto-3.dll kullanır, onlar kalır)
DROP = (
    "opengl32sw.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll",
    "qopensslbackend.dll", "qcertonlybackend.dll", "qtuiotouchplugin.dll", "qnetworklistmanager.dll",
    "qminimal.dll", "qoffscreen.dll", "qicns.dll", "qtga.dll", "qtiff.dll", "qwbmp.dll",
)


def _keep(entry):
    dest = entry[0].replace("\\", "/")
    name = dest.rsplit("/", 1)[-1].lower()
    if name in DROP:
        return False
    if "/translations/" in dest and name.endswith(".qm"):
        return name.endswith(("_tr.qm", "_en.qm"))
    return True


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tamga",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=os.path.join(SPECPATH, "version_info.txt"),
    icon=[os.path.join(ROOT, "tamga", "assets", "logo.ico")],
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="tamga")
