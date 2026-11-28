"""Windows güncellemeleri: Windows Update'in kendi COM arayüzü (Microsoft.Update.Session), PowerShell üzerinden.

Arama yönetici izni istemez (yaklaşık 30 sn sürer); kurma ve gizleme ister: yönetici PowerShell'i bir kez açılır,
ilerlemeyi bir durum dosyasına yazar, tamga o dosyayı okur. Gizlenen güncellemeyi Windows bir daha kendiliğinden
kurmaz (Ayarlar'da bunun düğmesi yok)."""
import json
import os
import subprocess
import tempfile

from .winget import NO_WINDOW, proc_close, proc_running, ps_quote, read_json, run_elevated_ps

SETTINGS = "ms-settings:windowsupdate"

# sınıflandırma kimlikleri (dilden bağımsız) -> tür
CLASSES = {
    "0fa1201d-4330-4fa8-8ae9-b877473b6441": "security",
    "e6cf1350-c01b-414d-a61f-263d14d133b4": "critical",
    "e0789628-ce08-4437-be74-2495b842f43b": "definition",
    "ebfc1fc5-71a4-4f7b-9aca-3b9a503104a0": "driver",
    "28bc880e-0592-4cbf-8f95-c79b17911d5f": "rollup",
    "cd5ffd1e-e932-4e3a-bf74-18bf0b1bbd83": "update",
    "b54e7d24-7add-428f-8b75-90a396fa584f": "feature",
    "68c5b0a3-d1a6-4553-ae49-01d3a7827828": "servicepack",
    "b4832bd8-e735-4761-8daf-37f882276dab": "tools",
    "3689bdc8-b205-4af4-8d4a-a63924c5e9d5": "upgrade",
}
# ResultCode: 2 başarılı, 3 hatalarla başarılı
OK_CODES = (2, 3)

_SEARCH = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
try {
  $s = New-Object -ComObject Microsoft.Update.Session
  $s.ClientApplicationID = 'tamga'
  $r = $s.CreateUpdateSearcher().Search("IsInstalled=0")
  $out = @(foreach ($u in $r.Updates) {
    [pscustomobject]@{
      id = [string]$u.Identity.UpdateID; title = [string]$u.Title; kb = (@($u.KBArticleIDs) -join ',')
      size = [int64]$u.MaxDownloadSize; hidden = [bool]$u.IsHidden; optional = [bool]$u.BrowseOnly
      downloaded = [bool]$u.IsDownloaded; severity = [string]$u.MsrcSeverity; type = [int]$u.Type
      cls = (@($u.Categories | Where-Object { $_.Type -eq 'UpdateClassification' } | ForEach-Object { $_.CategoryID }) -join ',')
      vendor = [string]$u.DriverManufacturer; url = [string](@($u.MoreInfoUrls)[0]); desc = [string]$u.Description
    } })
  $reboot = [bool](New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired
  @{ ok = $true; updates = $out; reboot = $reboot } | ConvertTo-Json -Depth 4 -Compress
} catch {
  @{ ok = $false; hr = [int64]$_.Exception.HResult; msg = [string]$_.Exception.Message } | ConvertTo-Json -Compress
}
"""

_FIND = r"""
$s = New-Object -ComObject Microsoft.Update.Session
$s.ClientApplicationID = 'tamga'
$ids = @({ids})
$crit = ($ids | ForEach-Object {{ "UpdateID='$_'" }}) -join ' or '
$found = @(); foreach ($u in $s.CreateUpdateSearcher().Search($crit).Updates) {{ $found += $u }}
"""

_INSTALL = r"""
$ErrorActionPreference = 'Stop'
$st = {status}; $res = @{{}}; $reboot = $false
function Put($o) {{
  $o.results = $res; $o.reboot = $reboot
  [IO.File]::WriteAllText("$st.tmp", ($o | ConvertTo-Json -Compress -Depth 4))
  Move-Item -LiteralPath "$st.tmp" -Destination $st -Force
}}
try {{
  Put @{{ phase = 'search' }}
{find}
  $n = $found.Count; $i = 0
  foreach ($u in $found) {{
    $i++; $id = [string]$u.Identity.UpdateID
    try {{
      if (-not $u.EulaAccepted) {{ $u.AcceptEula() }}
      $c = New-Object -ComObject Microsoft.Update.UpdateColl; [void]$c.Add($u)
      if (-not $u.IsDownloaded) {{
        Put @{{ phase = 'download'; i = $i; n = $n; id = $id }}
        $d = $s.CreateUpdateDownloader(); $d.Updates = $c; [void]$d.Download()
      }}
      Put @{{ phase = 'install'; i = $i; n = $n; id = $id }}
      $x = $s.CreateUpdateInstaller(); $x.Updates = $c; $r = $x.Install()
      $res[$id] = @{{ code = [int]$r.ResultCode; hr = [int64]$r.GetUpdateResult(0).HResult }}
      if ($r.RebootRequired) {{ $reboot = $true }}
    }} catch {{ $res[$id] = @{{ code = 4; hr = [int64]$_.Exception.HResult }} }}
  }}
  Put @{{ phase = 'done' }}
}} catch {{ Put @{{ phase = 'error'; hr = [int64]$_.Exception.HResult }} }}
"""

_HIDE = r"""
$ErrorActionPreference = 'Stop'
try {{
{find}
  foreach ($u in $found) {{ $u.IsHidden = {flag} }}
  exit 0
}} catch {{ exit 1 }}
"""


def kind(u):
    for c in (u.get("cls") or "").split(","):
        k = CLASSES.get(c.strip().lower())
        if k:
            return k
    return "driver" if u.get("type") == 2 else "update"


def important(u):
    return kind(u) in ("security", "critical") or (u.get("severity") or "") in ("Critical", "Important")


def default_selected(u):
    """Kendiliğinden seçili: zorunlu yazılım güncellemeleri. Sürücüler (Windows'unki çoğu zaman eski),
    isteğe bağlılar ve Windows sürüm yükseltmeleri elle seçilir."""
    return not u.get("hidden") and not u.get("optional") and kind(u) not in ("driver", "upgrade", "feature")


def parse(text):
    """Arama çıktısı -> (güncellemeler, yeniden başlatma bekliyor mu, hata kodu ya da 0)."""
    try:
        d = json.loads((text or "").strip() or "{}")
    except ValueError:
        return [], False, -1
    if not isinstance(d, dict) or not d.get("ok"):
        return [], False, int(d.get("hr") or -1) if isinstance(d, dict) else -1
    ups = d.get("updates") or []
    if isinstance(ups, dict):                       # PowerShell tek öğeyi dizi yapmayabilir
        ups = [ups]
    out = [u for u in ups if isinstance(u, dict) and u.get("id")]
    for u in out:
        u["kind"] = kind(u)
    return out, bool(d.get("reboot")), 0


def search():
    import base64
    enc = base64.b64encode(_SEARCH.encode("utf-16-le")).decode()
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-EncodedCommand", enc], capture_output=True, timeout=600, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return [], False, -1
    return parse(p.stdout.decode("utf-8", "replace"))


def _find(ids):
    return _FIND.format(ids=", ".join(ps_quote(i) for i in ids))


class Installer:
    """Seçilen güncellemeleri yönetici olarak indir ve kur (izin bir kez sorulur). poll() durum sözlüğü döner:
    {phase: search|download|install|done|error, i, n, id, results: {kimlik: {code, hr}}, reboot}."""

    def __init__(self):
        self.h = None
        self.status = ""

    def start(self, ids):
        self.status = os.path.join(tempfile.gettempdir(), f"tamga-wu-{os.getpid()}.json")
        try:
            os.remove(self.status)
        except OSError:
            pass
        script = _INSTALL.format(status=ps_quote(self.status), find=_find(ids))
        self.h, err = run_elevated_ps(script)
        return err

    def running(self):
        return proc_running(self.h)

    def poll(self):
        return read_json(self.status) if self.status else None

    def close(self):
        proc_close(self.h)
        self.h = None
        if self.status:
            try:
                os.remove(self.status)
            except OSError:
                pass


def set_hidden(ids, hidden=True):
    """Güncellemeleri gizle / yeniden göster (yönetici). -> 0 başarılı, 1223 izin verilmedi, başka: hata."""
    import ctypes
    h, err = run_elevated_ps(_HIDE.format(find=_find(ids), flag="$true" if hidden else "$false"))
    if not h:
        return err
    try:
        ctypes.windll.kernel32.WaitForSingleObject(h, 600000)
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        return code.value
    finally:
        proc_close(h)


def restart():
    subprocess.Popen(["shutdown", "/r", "/t", "0"], creationflags=NO_WINDOW)
