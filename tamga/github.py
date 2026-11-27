"""GitHub Releases: son sürüm bilgisi ve kurulum dosyasını indirme.
Yalnızca herkese açık sürüm bilgisi okunur, kimlik doğrulama ve kişisel bilgi gönderilmez."""
import json
import os
import re
import urllib.error
import urllib.request

from . import __version__
from . import apps as A

UA = f"tamga/{__version__}"


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def pick_asset(assets):
    """Kurulum dosyasını seçer: .exe, arm64 değil; "setup" ya da "x64" geçen öncelikli."""
    best, score = None, -1
    for a in assets or []:
        name = str(a.get("name", "")).lower()
        if not name.endswith(".exe") or "arm64" in name:
            continue
        s = 1 + ("setup" in name) * 2 + ("x64" in name) * 2 - ("portable" in name) * 2
        if s > score:
            best, score = a, s
    return best


def latest(repo):
    """{"version", "page", "asset_url", "asset_name", "size"}; sürüm yoksa / depo özelse {"error": "none"}."""
    try:
        with _get(f"https://api.github.com/repos/{repo}/releases/latest") as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"error": "none" if e.code == 404 else "rate" if e.code in (403, 429) else "net"}
    except Exception:
        return {"error": "net"}
    tag = str(data.get("tag_name", ""))
    m = re.search(r"\d+(?:\.\d+){0,2}", tag)
    a = pick_asset(data.get("assets"))
    return {
        "version": A.short(m.group(0)) if m else "",
        "page": str(data.get("html_url", f"https://github.com/{repo}/releases/latest")),
        "asset_url": a.get("browser_download_url", "") if a else "",
        "asset_name": a.get("name", "") if a else "",
        "size": int(a.get("size", 0) or 0) if a else 0,
        "notes": clean_notes(data.get("body")),
    }


def clean_notes(body, limit=4000):
    """Sürüm notları (Markdown): GitHub'ın kendiliğinden eklediği "Full Changelog" / imza satırları atılır;
    geriye bir şey kalmazsa ""."""
    keep = [ln for ln in str(body or "").replace("\r\n", "\n").split("\n")
            if not re.search(r"Full Changelog|Co-Authored-By|Generated with \[Claude", ln, re.I)]
    text = "\n".join(keep).strip()
    if not re.sub(r"(?m)^#+.*$", "", text).strip():       # yalnızca başlık ("## What's Changed") kaldıysa
        return ""
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] + "\n\n…"


def download(url, dest, progress=None, cancelled=lambda: False):
    """dest'e indirir (önce .part). progress(alınan, toplam)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            if cancelled():
                raise InterruptedError
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if progress:
                progress(got, total)
    if total and got != total:
        raise OSError("eksik indirme")
    os.replace(part, dest)
    return dest
