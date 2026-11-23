"""Arayüz metinleri: anahtar -> (Türkçe, English)."""
from .config import prefs

S = {
    "subtitle": ("tamga ailesi", "the tamga family"),
    "apps": ("Uygulamalar", "Apps"),
    "shared": ("Ortak ayarlar", "Shared settings"),
    "check": ("Güncellemeleri denetle", "Check for updates"),
    "checking": ("Denetleniyor…", "Checking…"),
    "open": ("Aç", "Open"),
    "install": ("Kur", "Install"),
    "update": ("Güncelle", "Update"),
    "cancel": ("İptal", "Cancel"),
    "installed_v": ("Kurulu {v}", "Installed {v}"),
    "not_installed": ("Kurulu değil", "Not installed"),
    "up_to_date": ("güncel", "up to date"),
    "new_v": ("yeni sürüm {v}", "new version {v}"),
    "latest_v": ("son sürüm {v}", "latest {v}"),
    "no_release": ("GitHub'da yayın yok", "no release on GitHub"),
    "net_error": ("GitHub'a ulaşılamadı", "couldn't reach GitHub"),
    "rate_error": ("GitHub sınırı, sonra dene", "GitHub limit, try later"),
    "running": ("açık", "running"),
    "downloading": ("İndiriliyor… {p}", "Downloading… {p}"),
    "installing": ("Kuruluyor…", "Installing…"),
    "dl_failed": ("İndirilemedi", "Download failed"),
    "inst_failed": ("Kurulum tamamlanmadı", "Installation didn't finish"),
    "releases_page": ("Sürüm sayfası", "Release page"),
    "theme": ("Tema", "Theme"),
    "dark": ("Koyu", "Dark"),
    "light": ("Açık", "Light"),
    "accent": ("Vurgu rengi", "Accent color"),
    "language": ("Dil", "Language"),
    "apply_to": ("Uygulanacaklar", "Apply to"),
    "applied_later": ("{a} açık: kapanınca uygulanır", "{a} is running: applied once it closes"),
    "applied": ("Uygulandı: {a}", "Applied: {a}"),
    "applied_none": ("Seçili uygulama yok", "No app selected"),
    "applied_live": ("Açık uygulamalar hemen değişir, dil yeniden başlatınca.",
                     "Open apps change right away, language after a restart."),
    "not_found": ("{a}: henüz tercih dosyası yok, ilk açılıştan sonra", "{a}: no preferences yet, after first launch"),
    "accent_gray": ("Gri", "Gray"), "accent_red": ("Kırmızı", "Red"), "accent_blue": ("Mavi", "Blue"),
    "accent_green": ("Yeşil", "Green"), "accent_orange": ("Turuncu", "Orange"), "accent_pink": ("Pembe", "Pink"),
    "accent_teal": ("Turkuaz", "Teal"),
    "update_close": ("{a} açık; kurulum onu kapatıp yeniden açacak.", "{a} is running; the installer will close and reopen it."),
    "continue": ("Devam", "Continue"),
}


def is_tr():
    return prefs.get("language", "tr") != "en"


def t(key, **kw):
    v = S.get(key)
    s = (v[0] if is_tr() else v[1]) if v else key
    return s.format(**kw) if kw else s
