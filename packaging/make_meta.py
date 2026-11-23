"""Derleme öncesi üretilen dosyalar: exe sürüm bilgisi (version_info.txt) ve kurulum sürümü (version.iss).

Kullanım: python packaging/make_meta.py   (build.ps1 otomatik çalıştırır; sürümü yazdırır)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from tamga import __version__  # noqa: E402

__author__ = "Yiğit Özsoy"

parts = [int(p) for p in __version__.split(".")[:3]]
ver4 = tuple((parts + [0, 0, 0, 0])[:4])
ver_str = ".".join(map(str, ver4))

VERSION_INFO = f"""# UTF-8 — make_meta.py tarafından üretildi
VSVersionInfo(
  ffi=FixedFileInfo(filevers={ver4}, prodvers={ver4}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', '{__author__}'),
      StringStruct('FileDescription', 'tamga'),
      StringStruct('FileVersion', '{ver_str}'),
      StringStruct('InternalName', 'tamga'),
      StringStruct('LegalCopyright', '© {__author__} — GPL-3.0'),
      StringStruct('OriginalFilename', 'tamga.exe'),
      StringStruct('ProductName', 'tamga'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1055, 1200])])
  ]
)
"""

# Kurulum sihirbazı görselleri (Inno Setup, %100 - %200 DPI), ailenin diğer kurulumlarıyla aynı düzen. Logo beyaz Göktürk t harfi; açık temada koyu boyanır.
WIZ_SCALES = (100, 125, 150, 175, 200)


def make_wizard_images():
    """build/wizard/ içine görselleri yazar; installer.iss için #define satırlarını döndürür."""
    from PIL import Image
    out = os.path.join(ROOT, "build", "wizard")
    os.makedirs(out, exist_ok=True)
    logo = Image.open(os.path.join(ROOT, "tamga", "assets", "logo.png")).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    names = {}
    for mode, color in (("light", (15, 15, 15)), ("dark", (255, 255, 255))):
        tinted = Image.new("RGBA", logo.size, color + (0,))
        tinted.putalpha(logo.getchannel("A"))
        # (tür, %100 boyutu, logo yüksekliği / kısa kenar, logonun dikey yeri (None = ortada))
        for kind, (W, H), frac, top in (("small", (58, 58), 0.62, None), ("large", (202, 386), 0.36, 0.30)):
            files = []
            for sc in WIZ_SCALES:
                w, h = W * sc // 100, H * sc // 100
                lh = int(min(w, h) * frac)
                lw = int(logo.width * lh / logo.height)
                img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                y = (h - lh) // 2 if top is None else int(h * top - lh / 2)
                img.alpha_composite(tinted.resize((lw, lh), Image.LANCZOS), ((w - lw) // 2, y))
                fn = f"{kind}_{mode}_{sc}.png"
                img.save(os.path.join(out, fn))
                files.append(os.path.join("..", "build", "wizard", fn))
            names[(kind, mode)] = ",".join(files)
    return "".join(f'#define {k} "{names[v]}"\n' for k, v in (
        ("WizSmall", ("small", "light")), ("WizSmallDark", ("small", "dark")),
        ("WizLarge", ("large", "light")), ("WizLargeDark", ("large", "dark"))))


if __name__ == "__main__":
    with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as f:
        f.write(VERSION_INFO)
    with open(os.path.join(HERE, "version.iss"), "w", encoding="utf-8-sig") as f:
        f.write(f'#define AppVersion "{__version__}"\n')
        f.write(make_wizard_images())
    print(__version__)
