"""Ortak ayarlar (tema, vurgu rengi, dil): her uygulamanın kendi tercih dosyasına yazılır.

kamug, erk, yazıt ve mergen aynı anahtarları kullanır:
  theme          tema çeşidi (amoled, dark_gray, graphite, midnight, mocha, white, light_gray, cream, ice, mint)
  dark_variant / light_variant   ailenin son seçilen çeşidi (tema düğmesi bununla geçiş yapar)
  accent         hazır ad (gray, red, blue …) ya da #rrggbb
  language       tr | en (uygulamalarda yeniden başlatınca uygulanır)
Açık olan uygulama dosyadaki değişikliği kendi tamga_sync modülüyle fark edip temayı hemen uygular.
bediz aynı tema / vurgu kimliklerini başka anahtar adlarıyla tutar (betaMonitorTheme, betaMonitorAccent);
canlı yenilemez, açıkken kaydettiği dosya üzerine yazacağı için yalnızca kapalıyken yazılır."""
from .apps import APPS
from .config import prefs, read_json, write_json
from .palette import ACCENTS, VARIANTS

KEYS = ("theme", "dark_variant", "light_variant", "accent", "language")


def prefs_path(app, create=False):
    """Var olan ilk tercih dosyası; create=True ise yoksa birincisi (klasörü uygulama oluşturmuş olmalı)."""
    import os
    for p in app.prefs:
        if os.path.isfile(p):
            return p
    if create and app.prefs and os.path.isdir(os.path.dirname(app.prefs[0])):
        return app.prefs[0]
    return None


def values():
    return {k: prefs.get(k) for k in KEYS}


def normalize(v):
    """Uygulamaların anlayacağı biçime getirir."""
    v = dict(v)
    theme = {"dark": "amoled", "light": "white"}.get(v.get("theme"), v.get("theme"))
    if theme not in VARIANTS:
        theme = "amoled"
    v["theme"] = theme
    v[VARIANTS[theme][2] + "_variant"] = theme
    for fam, default in (("dark", "amoled"), ("light", "white")):
        if v.get(fam + "_variant") not in VARIANTS or VARIANTS[v[fam + "_variant"]][2] != fam:
            v[fam + "_variant"] = default
    acc = str(v.get("accent") or "gray")
    if acc not in ACCENTS and not (acc.startswith("#") and len(acc) == 7):
        acc = "gray"
    v["accent"] = acc
    v["language"] = "en" if v.get("language") == "en" else "tr"
    return v


def seed():
    """İlk açılış: ortak ayarları ailenin mevcut tercihlerinden al (önce kamug, sonra yazıt, erk). Aileye sonradan
    katılan uygulama (ör. mergen) bir kez "Uygulanacaklar" listesine eklenir."""
    seen = prefs.get("sync_seen") or ["kamug", "erk", "yazit", "bediz"]
    new = [a.id for a in APPS if a.shares_theme and a.id not in seen]
    if new:
        prefs.set("sync_apps", list(prefs.get("sync_apps") or []) + [x for x in new if x not in (prefs.get("sync_apps") or [])])
    if new or not prefs.get("sync_seen"):
        prefs.set("sync_seen", [a.id for a in APPS])
    if prefs.get("seeded"):
        return
    for aid in ("kamug", "yazit", "erk"):
        app = next(a for a in APPS if a.id == aid)
        p = prefs_path(app)
        d = read_json(p) if p else None
        if d and d.get("theme"):
            prefs.update(normalize({k: d.get(k, prefs.get(k)) for k in KEYS}))
            break
    prefs.set("seeded", True)


def _mapped(app, v):
    if not app.key_map:
        return {k: v[k] for k in KEYS}
    return {app.key_map[k]: v[k] for k in KEYS if k in app.key_map}


def apply_to(app, v=None, running=False):
    """Ortak ayarları bir uygulamanın tercih dosyasına yazar.
    Dönüş: "ok" | "same" | "missing" | "running" (canlı yenilemeyen uygulama açık) | "error"."""
    if not app.shares_theme:
        return "missing"
    v = _mapped(app, normalize(v or values()))
    path = prefs_path(app, create=True)
    if not path:
        return "missing"
    d = read_json(path)
    if d is None:
        d = {}
    if all(d.get(k) == x for k, x in v.items()):
        return "same"
    if running and not app.live:
        return "running"
    d.update(v)
    try:
        write_json(path, d, indent=app.indent)
    except OSError:
        return "error"
    return "ok"


def apply_all(v=None, running=()):
    """Seçili uygulamalara uygular: {uygulama: durum}. running: açık uygulamaların kimlikleri."""
    sel = set(prefs.get("sync_apps") or [])
    return {a.id: apply_to(a, v, a.id in running) for a in APPS if a.shares_theme and a.id in sel}


def current_for(app):
    """Uygulamanın tercih dosyasındaki tema/vurgu/dil (yoksa None)."""
    p = prefs_path(app)
    d = read_json(p) if p else None
    if d is None:
        return None
    return {k: d.get(k) for k in KEYS}
