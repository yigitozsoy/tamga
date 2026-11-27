"""Diğer uygulamaların güncellemeleri: Windows'un kendi paket yöneticisi winget.

`winget upgrade` tablosu okunur (sütun başlıkları dile göre değişir, bu yüzden adlarla değil konumlarla);
güncelleme `winget upgrade --id <kimlik> --exact --silent` ile, sırayla yapılır."""
import re
import shutil
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
STORE_UPDATES = "ms-windows-store://downloadsandupdates"
WINGET_STORE = "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1"     # Uygulama Yükleyici (winget)

_PCT = re.compile(r"(\d{1,3})\s*%")


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
    """-> (liste, hata). hata: "" | "missing" | "fail"."""
    w = exe()
    if not w:
        return [], "missing"
    try:
        p = subprocess.run([w, "upgrade", "--include-unknown", "--accept-source-agreements",
                            "--disable-interactivity"], capture_output=True, timeout=180, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return [], "fail"
    rows = parse_upgrades(p.stdout.decode("utf-8", "replace"))
    return rows, ("" if rows or p.returncode in (0, -1978335212) else "fail")   # 0x8A150014: güncelleme yok


def upgrade(pid, on_pct=None):
    """Tek paketi sessizce güncelle; ilerleme yüzdesini on_pct(0..100) ile bildirir. -> çıkış kodu."""
    w = exe()
    if not w:
        return -1
    args = [w, "upgrade", "--id", pid, "--exact", "--silent", "--include-unknown",
            "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"]
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError:
        return -1
    buf = b""
    while True:
        ch = p.stdout.read(256)
        if not ch:
            break
        buf = (buf + ch)[-512:]
        m = None
        for m in _PCT.finditer(buf.decode("utf-8", "replace")):
            pass
        if m and on_pct:
            on_pct(min(100, int(m.group(1))))
    return p.wait()
