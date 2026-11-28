# tamga — Claude için proje notları

**tamga**: Yiğit Özsoy'un Windows uygulama ailesinin (erk, bediz, kamug, yazıt) başlatıcısı. PyQt6, yalnızca Windows 10/11 64-bit.
Kullanıcıyla çalışma tarzı (Türkçe, sade varsayılanlar, gri vurgu, mor yok, eski adlar gamma/alpha/beta/delta hiçbir yerde
görünmesin, derleme/commit/push yalnızca istenince) kamug'un CLAUDE.md'siyle aynı: `..\kamug\CLAUDE.md` bölüm 2.

## Yapı
```
main.py               kaynaktan başlatıcı
tamga/app.py          tek örnek (QLocalServer "tamga-launcher-<kullanıcı>")
tamga/window.py       kartlar (kur / aç / güncelle), ortak ayarlar, indirme + Inno kurulumu (/SILENT /CLOSEAPPLICATIONS)
tamga/apps.py         katalog (AppId, repo, exe, tercih dosyası), kurulu algılama, çalışan süreçler
tamga/github.py       Releases API (kimliksiz), kurulum dosyası seçimi (.exe, x64/setup, arm64 değil), indirme
tamga/winget.py       "Diğer uygulamalar" sekmesi: `winget upgrade` tablosunu konumla okur (başlık dile göre değişir), sırayla sessiz güncelleme,
                      önerilenler (RECOMMENDED: Microsoft.* + güvenlik), simge (kaldırma kaydı DisplayIcon / InstallLocation),
                      boyut (`winget show` SHA256 üstündeki adres + HEAD), indirme ilerlemesi (%TEMP%\WinGet\<id>.<sürüm>, os.stat)
tamga/winupdate.py   Windows Update COM'u (Microsoft.Update.Session) PowerShell ile: arama (yöneticisiz, ~30 sn, JSON),
                      kurma (yönetici PowerShell bir kez, ilerleme durum dosyasında), gizleme; tür sınıflandırma kimliğinden
tamga/wu_tab.py       "Windows" sekmesi (WuPage): seç / kur / gizle, ilerleme kartı, yeniden başlatma
tamga/shared.py       ortak anahtarları uygulamaların tercih dosyasına yazar
tamga/palette.py      yazıt/erk/kamug ile birebir aynı tema çeşitleri ve vurgular (yazıt theme.py'den kopya)
sync/tamga_sync.py    kamug/erk/yazıt içindeki tamga_sync.py'nin ana kopyası (smoke test eşliği denetler)
packaging/            build.ps1, tamga.spec, installer.iss (AppId {FB53E9DE-E7AE-4660-8910-541D2D3F23BF}), make_meta.py, make_logo.py
```

## Bilinen tuzaklar
- Ortak anahtarlar: `theme` (çeşit kimliği), `dark_variant`, `light_variant`, `accent` (ad ya da #hex), `language`.
  Uygulamalar tercihleri bellekte tutar ve her `set`'te tüm dosyayı yazar; bu yüzden açık uygulama dosyayı
  `tamga_sync` (klasör izleyici, 200 ms) ile yeniden okur, yoksa tamga'nın yazdığını ezerdi. Dil yeniden başlatınca.
- tamga tercih dosyası olmayan uygulamaya yazmaz (kamug'un gamma → kamug klasör taşıması bozulmasın).
- bediz .NET: aynı tema çeşitleri / vurgular `%APPDATA%\bediz\settings.json` içinde `betaMonitorTheme` /
  `betaMonitorAccent` adıyla (dil yok). Canlı yenilemez ve açıkken kendi kaydıyla ezer: yalnızca kapalıyken yazılır
  (`App.live=False`; pencere 3 sn'lik yoklamada bediz kapanınca uygular).
- erk deposu özel: Releases API 404 → "GitHub'da yayın yok".
- Kayıt defteri: Claude masaüstü ve Python install manager MSIX; kaynaktan çalışırken başlatılan kurulumlar
  sanal kayıt defterine yazabilir. Gerçek denetim için `Invoke-CimMethod Win32_Process Create`. Kurulu tamga.exe'de sorun yok.
- winget çıktısı yönlendirilince ilerleme çubuğu / yüzde YAZMAZ: aşama satırlardan ("Downloading https://…" sonra
  doğrulama), yüzde geçici klasördeki dosyanın boyutundan. Dizin kaydı yazılırken güncellenmez: `scandir` değil `os.stat`.
- winget `--silent` yönetici izni penceresi açmaz: herkes için kurulu MSI'lar 1603 / 0x8A150049 ile düşer. Neden
  `winget.reason(kod)`. Yönetici kipi (`wg_admin`, varsayılan açık): HKLM'de kayıtlı paketler `AdminRunner`'a gider —
  runas ile bir kez açılan PowerShell, job.json / result.json ile sıradaki tüm paketleri kurar, `--scope machine`,
  uygun kurulum yoksa kapsamsız yeniden. HKCU'dakiler (Discord, Spotify: yönetici olarak kurulmayı reddeder) normal. Hata ayıklama: winget günlükleri
  `%LOCALAPPDATA%\Packages\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe\LocalState\DiagOutputDir`.
- Sürüm notu: build.yml etiketlenen commit'in mesajını yayın gövdesi yapar; commit mesajını sürüm notu gibi yaz.
- Test: `python tests/smoke_test.py` (LOCALAPPDATA ve TAMGA_DATA_DIR geçici klasöre, ağ sahte, pencere ekranda değil).
