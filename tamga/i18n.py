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
    "tab_family": ("tamga uygulamaları", "tamga apps"),
    "tab_other": ("Diğer uygulamalar", "Other apps"),
    "updates": ("Güncellemeler", "Updates"),
    "update_all": ("Tümünü güncelle", "Update all"),
    "wg_ver": ("{v}  →  {n}", "{v}  →  {n}"),
    "wg_queued": ("Sırada", "Queued"),
    "wg_updating": ("Güncelleniyor… {p}", "Updating… {p}"),
    "wg_failed": ("Güncellenemedi; uygulama açıksa kapatıp yeniden dene", "Update failed; close the app if it's open and retry"),
    "wg_none": ("Hepsi güncel", "Everything is up to date"),
    "wg_never": ("Henüz denetlenmedi", "Not checked yet"),
    "wg_count": ("{n} güncelleme var", "{n} updates available"),
    "wg_checked": ("son denetim {t}", "checked {t}"),
    "wg_missing": ("winget bulunamadı. Microsoft Store'dan \"Uygulama Yükleyici\"yi kur ya da güncelle.",
                   "winget not found. Install or update \"App Installer\" from the Microsoft Store."),
    "wg_fail": ("winget çalıştırılamadı", "couldn't run winget"),
    "get_winget": ("Uygulama Yükleyici", "App Installer"),
    "wg_hint": ("Bilgisayardaki tüm uygulamalar Windows'un paket yöneticisi winget ile denetlenir; güncelleme sessizce, "
                "sırayla kurulur. Bazı kurulumlar yönetici izni isteyebilir.",
                "Every app on this PC is checked with winget, Windows' package manager; updates install silently, "
                "one at a time. Some installers may ask for admin rights."),
    "store": ("Microsoft Store uygulamaları", "Microsoft Store apps"),
    "store_desc": ("WhatsApp, Spotify gibi Store'dan kurulanlar Store'un kendi güncelleyicisiyle güncellenir.",
                   "Apps installed from the Store, like WhatsApp or Spotify, update through the Store itself."),
    "store_open": ("Store'da güncelle", "Update in Store"),
    "just_now": ("az önce", "just now"),
    "min_ago": ("{n} dk önce", "{n} min ago"),
    "hour_ago": ("{n} sa önce", "{n} h ago"),
    "day_ago": ("{n} gün önce", "{n} d ago"),
}


def is_tr():
    return prefs.get("language", "tr") != "en"


def t(key, **kw):
    v = S.get(key)
    s = (v[0] if is_tr() else v[1]) if v else key
    return s.format(**kw) if kw else s
