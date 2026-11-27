"""Ana pencere: uygulama kartları (kur / aç / güncelle) ve ortak ayarlar."""
import os
import subprocess
import threading
import time

from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QFileInfo, QObject, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QFileIconProvider, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
                             QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from . import REPO, __version__
from . import apps as A
from . import github, shared, theme
from . import winget as W
from .config import DOWNLOAD_DIR, asset, prefs
from .i18n import is_tr, t
from .palette import ACCENTS, VARIANTS

CHECK_EVERY = 3600          # GitHub'a en fazla saatte bir (elle denetim hariç)
SELF = "tamga"              # tamga'nın kendi sürüm kaydı (self.rel / self.jobs anahtarı)


class Bus(QObject):
    """İş parçacıklarından ana iş parçacığına."""
    release = pyqtSignal(str, dict)
    check_done = pyqtSignal()
    progress = pyqtSignal(str, int, int)
    downloaded = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)
    wg_list = pyqtSignal(list, str)
    wg_phase = pyqtSignal(str, str)
    wg_done = pyqtSignal(str, int)
    wg_size = pyqtSignal(str, str, int)


WG_OK = (0, -1978335189)    # 0x8A15002B: uygulanabilir güncelleme yok (zaten güncel / daha yeni)


def fmt_size(n):
    """Bayt -> "85 MB" / "1,4 GB" ("" bilinmiyorsa)."""
    if not n or n <= 0:
        return ""
    if n < 1024 ** 2:
        txt = f"{max(1, round(n / 1024))} KB"
    elif n < 1024 ** 3:
        txt = f"{round(n / 1024 ** 2)} MB"
    else:
        txt = f"{n / 1024 ** 3:.1f} GB"
    return txt.replace(".", ",") if is_tr() else txt


def fmt_pct(p):
    return f"%{p}" if is_tr() else f"{p}%"


def ago(ts):
    s = max(0, time.time() - ts)
    if s < 60:
        return t("just_now")
    if s < 3600:
        return t("min_ago", n=int(s // 60))
    if s < 86400:
        return t("hour_ago", n=int(s // 3600))
    return t("day_ago", n=int(s // 86400))


# --- küçük parçalar ----------------------------------------------------------

class VariantSwatch(QAbstractButton):
    """Tema çeşidinin küçük önizlemesi (zemin, yüzey, metin çizgileri, vurgu noktası) ve adı."""

    def __init__(self, vid, parent=None):
        super().__init__(parent)
        self.vid = vid
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(112, 92)
        v = VARIANTS[vid]
        self.setToolTip(v[0] if is_tr() else v[1])

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = theme.variant_palette(self.vid)
        box = QRectF(4, 3, self.width() - 8, 58)
        if self.isChecked():
            p.setPen(QPen(theme.qcolor(theme.accent()), 2.5))
        elif self.underMouse():
            p.setPen(QPen(theme.qcolor(theme.color("text3")), 1.5))
        else:
            p.setPen(QPen(theme.qcolor(theme.color("divider")), 1))
        p.setBrush(theme.qcolor(c["bg"]))
        p.drawRoundedRect(box, 10, 10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.qcolor(c["surface"]))
        p.drawRoundedRect(QRectF(box.x() + 10, box.y() + 10, box.width() - 20, 14), 4, 4)
        p.setBrush(theme.qcolor(c["text"]))
        p.drawRoundedRect(QRectF(box.x() + 10, box.y() + 32, 44, 5), 2.5, 2.5)
        p.setBrush(theme.qcolor(c["text2"]))
        p.drawRoundedRect(QRectF(box.x() + 10, box.y() + 42, 30, 5), 2.5, 2.5)
        p.setBrush(theme.qcolor(theme.accent()))
        p.drawEllipse(QRectF(box.right() - 22, box.y() + 33, 12, 12))
        p.setPen(theme.qcolor(theme.color("text" if self.isChecked() else "text2")))
        f = p.font()
        f.setPointSizeF(9)
        f.setWeight(600 if self.isChecked() else 400)
        p.setFont(f)
        p.drawText(QRectF(0, 64, self.width(), 24), Qt.AlignmentFlag.AlignCenter, self.toolTip())

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class AccentSwatch(QAbstractButton):
    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 36)
        self.setToolTip(t("accent_" + key))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            p.setPen(QPen(theme.qcolor(theme.color("text")), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(2, 2, 32, 32))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.qcolor(ACCENTS[self.key]))
        p.drawEllipse(QRectF(7, 7, 22, 22))


class AppCard(QFrame):
    def __init__(self, app, win):
        super().__init__()
        self.app = app
        self.win = win
        self.setObjectName("Card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 14, 14)
        lay.setSpacing(16)

        self.logo = QLabel()
        self.logo.setFixedSize(44, 44)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dpr = win.devicePixelRatioF()
        self.logo.setPixmap(theme.tinted(app.logo, 34, dpr))
        lay.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignTop)     # yenilikler açılınca yukarıda kalsın

        mid = QVBoxLayout()
        mid.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(10)
        name = QLabel(app.name)
        name.setObjectName("AppName")
        desc = QLabel(app.desc[0] if is_tr() else app.desc[1])
        desc.setObjectName("Muted")
        top.addWidget(name)
        top.addWidget(desc)
        top.addStretch(1)
        mid.addLayout(top)
        self.status = QLabel()
        self.status.setObjectName("Status")
        mid.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1000)
        self.bar.hide()
        mid.addWidget(self.bar)
        self.notes = QLabel()
        self.notes.setObjectName("Notes")
        self.notes.setTextFormat(Qt.TextFormat.MarkdownText)
        self.notes.setWordWrap(True)
        self.notes.setOpenExternalLinks(True)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.notes.hide()
        mid.addWidget(self.notes)
        lay.addLayout(mid, 1)

        # sürüm notu varsa "Yenilikler" (kartta açılır), yoksa "Sürüm sayfası" (tarayıcıda)
        self.btn_page = QPushButton(t("releases_page"))
        self.btn_page.setObjectName("Link")
        self.btn_page.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page.clicked.connect(self._page)
        self.btn_act = QPushButton()
        self.btn_act.setObjectName("Primary")
        self.btn_act.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_act.clicked.connect(lambda: self.win.install(app.id))
        self.btn_open = QPushButton(t("open"))
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(lambda: self.win.launch(app.id))
        for b in (self.btn_page, self.btn_act, self.btn_open):
            lay.addWidget(b)
        self.refresh()

    def _page(self):
        rel = self.win.rel.get(self.app.id) or {}
        if rel.get("notes"):
            self.notes.setVisible(not self.notes.isVisible())
            self.refresh()
        else:
            QDesktopServices.openUrl(QUrl(rel.get("page") or f"https://github.com/{self.app.repo}/releases"))

    def refresh(self):
        w, aid = self.win, self.app.id
        inst, rel, job = w.inst.get(aid), w.rel.get(aid) or {}, w.jobs.get(aid)
        parts, state = [], ""
        rv = rel.get("version", "")
        if inst:
            parts.append(t("installed_v", v=inst.version or "?"))
            if rv and A.is_newer(rv, inst.version):
                parts.append(t("new_v", v=rv))
                if fmt_size(rel.get("size")):
                    parts.append(fmt_size(rel.get("size")))
                state = "new"
            elif rv:
                parts.append(t("up_to_date"))
            if aid in w.running:
                parts.append(t("running"))
        else:
            parts.append(t("not_installed"))
            if rv:
                parts.append(t("latest_v", v=rv))
                if fmt_size(rel.get("size")):
                    parts.append(fmt_size(rel.get("size")))
        err = rel.get("error")
        if err:
            parts.append(t({"none": "no_release", "rate": "rate_error"}.get(err, "net_error")))
            state = state or "err"
        self.status.setText("  ·  ".join(parts))
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        can_get = bool(rel.get("asset_url")) and (not inst or A.is_newer(rv, inst.version))
        if job:
            self.btn_act.setVisible(True)
            self.btn_act.setEnabled(False)
            if job["phase"] == "download":
                pct = f"%{job['p'] // 10}" if is_tr() else f"{job['p'] // 10}%"
                self.btn_act.setText(t("downloading", p=pct if job["p"] >= 0 else ""))
                self.bar.setVisible(True)
                self.bar.setValue(max(0, job["p"]))
            else:
                self.btn_act.setText(t("installing"))
                self.bar.setVisible(False)
        else:
            self.bar.setVisible(False)
            self.btn_act.setEnabled(True)
            self.btn_act.setVisible(can_get)
            self.btn_act.setText(t("update") if inst else t("install"))
        notes = rel.get("notes") or ""
        if notes:
            page = rel.get("page") or f"https://github.com/{self.app.repo}/releases"
            self.notes.setText(f"{notes}\n\n[{t('releases_page')}]({page})")
            self.btn_page.setText(t("notes_hide") if self.notes.isVisible() else t("notes"))
        else:
            self.notes.hide()
            self.btn_page.setText(t("releases_page"))
        self.btn_page.setVisible(bool(rel.get("page")) and not job)
        self.btn_open.setVisible(bool(inst))
        self.btn_open.setEnabled(not job)


def pkg_pixmap(path, name, px, dpr):
    """Kurulu uygulamanın simgesi; yoksa adın baş harfi yuvarlak köşeli karede."""
    if path and os.path.isfile(path):
        ic = QIcon(path) if path.lower().endswith(".ico") else QFileIconProvider().icon(QFileInfo(path))
        pm = ic.pixmap(QSize(px, px), dpr)
        if not pm.isNull():
            return pm
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.qcolor(theme.color("surface")))
    p.drawRoundedRect(QRectF(0, 0, px * dpr, px * dpr), 7 * dpr, 7 * dpr)
    p.setPen(theme.qcolor(theme.color("text2")))
    f = p.font()
    f.setPixelSize(int(px * dpr * 0.5))
    f.setWeight(600)
    p.setFont(f)
    letter = next((ch for ch in (name or "") if ch.isalnum()), "?").upper()
    p.drawText(QRectF(0, 0, px * dpr, px * dpr), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


class WgRow(QWidget):
    """Diğer uygulamalar sekmesinde winget'in bildirdiği tek güncelleme."""

    def __init__(self, item, win):
        super().__init__()
        self.item = item
        self.win = win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 14, 10)
        lay.setSpacing(14)
        self.icon = QLabel()
        self.icon.setFixedSize(30, 30)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setPixmap(win.pkg_icon(item))
        lay.addWidget(self.icon)
        mid = QVBoxLayout()
        mid.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(item["name"])
        name.setObjectName("RowName")
        name.setToolTip(item["id"])
        top.addWidget(name)
        if W.recommended(item["id"]):
            badge = QLabel(t("recommended"))
            badge.setObjectName("Badge")
            badge.setToolTip(t("update_rec_tip"))
            top.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        mid.addLayout(top)
        self.status = QLabel()
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        mid.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.hide()
        mid.addWidget(self.bar)
        lay.addLayout(mid, 1)
        self.btn_menu = QPushButton()
        self.btn_menu.setObjectName("Link")
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self._menu)
        lay.addWidget(self.btn_menu)
        self.btn = QPushButton(t("update"))
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._act)
        lay.addWidget(self.btn)
        self.refresh()

    def _act(self):
        pid = self.item["id"]
        if (self.win.wg_jobs.get(pid) or {}).get("phase") == "queued":
            self.win.dequeue(pid)
        else:
            self.win.update_pkg(pid)

    def _menu(self):
        it, w = self.item, self.win
        if w.wg_hidden(it):
            w.unhide(it["id"])
            return
        m = QMenu(self)
        if it.get("available"):
            m.addAction(t("wg_skip", v=it["available"]), lambda: w.skip(it["id"], it["available"]))
        m.addAction(t("wg_ignore"), lambda: w.ignore(it["id"]))
        m.exec(self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomLeft()))

    def refresh(self):
        w, pid, it = self.win, self.item["id"], self.item
        job = w.wg_jobs.get(pid)
        parts = [t("wg_ver", v=it.get("version") or "?", n=it.get("available") or "?")]
        sz = fmt_size(w.wg_size_of(it))
        if sz:
            parts.append(sz)
        state = ""
        hidden = w.wg_hidden(it)
        if hidden:
            parts.append(t("wg_ignored") if pid in (prefs.get("wg_ignore") or []) else t("wg_skipped"))
        elif pid in w.wg_failed:
            parts.append(t("wg_failed"))
            state = "err"
        self.status.setText("  ·  ".join(parts))
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.btn_menu.setVisible(not job)
        self.btn_menu.setText(t("wg_unhide") if hidden else t("wg_hide"))
        self.btn.setVisible(not hidden)
        self.btn.setToolTip("")
        phase = job["phase"] if job else ""
        if phase == "queued":
            self.btn.setEnabled(True)
            self.btn.setText(t("wg_queued_n", n=w.queue_pos(pid)))
            self.btn.setToolTip(t("wg_dequeue_tip"))
            self.bar.hide()
        elif phase:
            self.btn.setEnabled(False)
            p = job.get("p", -1)
            if phase == "download":
                got = fmt_pct(p) if p >= 0 else fmt_size(job.get("got", 0))
                self.btn.setText(t("downloading", p=got))
            else:
                self.btn.setText(t("installing") if phase == "install" else t("wg_starting"))
            busy = phase != "download" or p < 0
            self.bar.setRange(0, 0 if busy else 100)       # 0..0: belirsiz (kayan) çubuk
            if not busy:
                self.bar.setValue(p)
            self.bar.show()
        else:
            self.btn.setEnabled(True)
            self.btn.setText(t("update"))
            self.bar.hide()


# --- ana pencere -------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("tamga")
        self.setWindowIcon(QIcon(asset("logo.ico")))
        self.setMinimumSize(640, 560)
        self.bus = Bus()
        self.bus.release.connect(self._on_release)
        self.bus.check_done.connect(self._on_check_done)
        self.bus.progress.connect(self._on_progress)
        self.bus.downloaded.connect(self._on_downloaded)
        self.bus.failed.connect(self._on_failed)
        self.bus.wg_list.connect(self._on_wg_list)
        self.bus.wg_phase.connect(self._on_wg_phase)
        self.bus.wg_done.connect(self._on_wg_done)
        self.bus.wg_size.connect(self._on_wg_size)
        self.inst, self.running, self.jobs, self.cards = {}, set(), {}, {}
        self.rel = dict(prefs.get("releases") or {})
        self._checking = False
        self._procs = {}
        self._cancel = set()
        self._status_msg = ""
        # diğer uygulamalar (winget)
        self.tab = 1 if prefs.get("tab") == 1 else 0
        self.wg = [x for x in (prefs.get("wg_upgrades") or []) if isinstance(x, dict) and x.get("id")]
        self.wg_err = ""
        self.wg_jobs, self.wg_failed, self.wg_rows = {}, set(), {}
        self._wg_checking = False
        self._wg_q, self._wg_lock, self._wg_worker = [], threading.Lock(), False
        self.wg_sizes = {k: v for k, v in (prefs.get("wg_sizes") or {}).items() if isinstance(v, list) and len(v) == 2}
        self._wg_sizing = False
        self.wg_show_hidden = False
        self.wg_batch = {"total": 0, "done": 0, "ok": 0, "fail": 0}
        self.wg_summary = ""
        self._icons = {}
        self.wg_tick = QTimer(self)
        self.wg_tick.timeout.connect(self._wg_tick)

        shared.seed()
        self._clean_downloads()
        self.scan()
        self.build()
        geo = prefs.get("window_geometry")
        if isinstance(geo, list) and len(geo) == 4:
            self.setGeometry(*geo)
        else:
            self.resize(780, 860)

        self.poll = QTimer(self)
        self.poll.timeout.connect(self._poll)
        self.poll.start(3000)
        # yeni sürüme güncellenince (ya da saatte bir) hemen denetle: yeni eklenen uygulamaların durumu da gelsin
        fresh = prefs.get("last_version") != __version__
        prefs.set("last_version", __version__)
        if fresh or time.time() - float(prefs.get("releases_checked", 0) or 0) > CHECK_EVERY:
            QTimer.singleShot(300, self.check_updates)
        if time.time() - float(prefs.get("wg_checked", 0) or 0) > CHECK_EVERY:
            QTimer.singleShot(800, self.check_other)
        else:
            QTimer.singleShot(800, self._fetch_sizes)

    # -- durum
    def scan(self):
        exes = A.running_exes()
        self.running = set()
        for a in A.APPS:
            inst = A.installed(a)
            self.inst[a.id] = inst
            if A.is_running(inst, exes):
                self.running.add(a.id)

    def _poll(self):
        before = ({k: (v.version if v else None) for k, v in self.inst.items()}, set(self.running))
        self.scan()
        self._check_installers()
        # canlı yenilemeyen uygulama (bediz) kapanınca bekleyen ortak ayarları yaz
        sel = set(prefs.get("sync_apps") or [])
        for a in A.APPS:
            if a.shares_theme and not a.live and a.id in sel and a.id not in self.running and self.inst.get(a.id):
                shared.apply_to(a)
        after = ({k: (v.version if v else None) for k, v in self.inst.items()}, set(self.running))
        if before != after:
            self.refresh_cards()
        try:
            self._refresh_wg_status()          # "son denetim N dk önce" eskimesin
        except RuntimeError:
            pass

    def refresh_cards(self):
        for c in self.cards.values():
            c.refresh()

    # -- arayüz
    def build(self):
        self._icons = {}                     # harf simgeleri temanın renginde
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self._dark_titlebar()
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        top = QWidget()
        tlay = QVBoxLayout(top)
        tlay.setContentsMargins(32, 26, 32, 10)
        tlay.setSpacing(14)
        outer.addWidget(top)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        def page():
            scroll = QScrollArea()
            scroll.setObjectName("Scroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.stack.addWidget(scroll)
            body = QWidget()
            scroll.setWidget(body)
            pl = QVBoxLayout(body)
            pl.setContentsMargins(32, 8, 32, 32)
            pl.setSpacing(10)
            return pl
        lay = page()

        head = QHBoxLayout()
        head.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(theme.tinted(asset("logo.png"), 34, self.devicePixelRatioF()))
        head.addWidget(logo)
        title = QLabel("tamga")
        title.setObjectName("Title")
        head.addWidget(title)
        self.lbl_ver = QLabel()
        self.lbl_ver.setObjectName("Status")
        head.addWidget(self.lbl_ver, 0, Qt.AlignmentFlag.AlignBottom)
        head.addSpacing(4)
        self.btn_self = QPushButton()
        self.btn_self.setObjectName("Primary")
        self.btn_self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_self.clicked.connect(self.update_self)
        head.addWidget(self.btn_self)
        self.btn_self_notes = QPushButton(t("notes"))
        self.btn_self_notes.setObjectName("Link")
        self.btn_self_notes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_self_notes.clicked.connect(self._self_notes)
        head.addWidget(self.btn_self_notes)
        head.addStretch(1)
        self.btn_check = QPushButton()
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.clicked.connect(
            lambda: self.check_updates(force=True) if self.tab == 0 else self.check_other())
        head.addWidget(self.btn_check)
        tlay.addLayout(head)

        trow = QHBoxLayout()
        trow.setSpacing(6)
        tgrp = QButtonGroup(top)
        self.tabs = []
        for i, key in enumerate(("tab_family", "tab_other")):
            b = QPushButton(t(key))
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, i=i: self.set_tab(i))
            tgrp.addButton(b)
            trow.addWidget(b)
            self.tabs.append(b)
        trow.addStretch(1)
        tlay.addLayout(trow)

        lay.addWidget(self._section(t("apps")))
        self.cards = {}
        for a in A.APPS:
            card = AppCard(a, self)
            self.cards[a.id] = card
            lay.addWidget(card)

        lay.addSpacing(18)
        lay.addWidget(self._section(t("shared")))
        lay.addWidget(self._settings_card())
        lay.addStretch(1)
        self._build_other(page())
        self._refresh_self()
        self.set_tab(self.tab, save=False)
        old = self.centralWidget()
        self.setCentralWidget(root)
        if old:
            old.deleteLater()

    def _section(self, text):
        lb = QLabel(text)
        lb.setObjectName("Section")
        lb.setContentsMargins(4, 0, 0, 4)
        return lb

    # -- sekmeler
    def set_tab(self, i, save=True):
        self.tab = i
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.tabs):
            b.setChecked(k == i)
        if save:
            prefs.set("tab", i)
        self._refresh_check_btn()

    def _refresh_check_btn(self):
        try:
            busy = self._checking if self.tab == 0 else self._wg_checking
            self.btn_check.setEnabled(not busy)
            self.btn_check.setText(t("checking") if busy else t("check"))
        except (RuntimeError, AttributeError):
            pass

    # -- diğer uygulamalar (winget)
    def _build_other(self, lay):
        hrow = QHBoxLayout()
        hrow.setSpacing(8)
        hrow.addWidget(self._section(t("updates")))
        hrow.addStretch(1)
        self.btn_rec = QPushButton(t("update_rec"))
        self.btn_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec.setToolTip(t("update_rec_tip"))
        self.btn_rec.clicked.connect(self.update_recommended)
        hrow.addWidget(self.btn_rec, 0, Qt.AlignmentFlag.AlignBottom)
        self.btn_all = QPushButton(t("update_all"))
        self.btn_all.setObjectName("Primary")
        self.btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all.clicked.connect(self.update_all)
        hrow.addWidget(self.btn_all, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(hrow)
        srow = QHBoxLayout()
        srow.setContentsMargins(4, 0, 0, 0)
        self.wg_status = QLabel()
        self.wg_status.setObjectName("Status")
        self.wg_status.setWordWrap(True)
        srow.addWidget(self.wg_status, 1)
        self.btn_hidden = QPushButton()
        self.btn_hidden.setObjectName("Link")
        self.btn_hidden.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hidden.clicked.connect(self._toggle_hidden)
        srow.addWidget(self.btn_hidden)
        self.btn_getwg = QPushButton(t("get_winget"))
        self.btn_getwg.setObjectName("Link")
        self.btn_getwg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_getwg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(W.WINGET_STORE)))
        srow.addWidget(self.btn_getwg)
        lay.addLayout(srow)

        # sıra: birden çok güncelleme sırayla kurulurken genel ilerleme
        self.q_card = QFrame()
        self.q_card.setObjectName("Card")
        ql = QVBoxLayout(self.q_card)
        ql.setContentsMargins(20, 14, 14, 14)
        ql.setSpacing(6)
        qtop = QHBoxLayout()
        self.q_title = QLabel()
        self.q_title.setObjectName("RowName")
        qtop.addWidget(self.q_title, 1)
        self.q_count = QLabel()
        self.q_count.setObjectName("Status")
        qtop.addWidget(self.q_count)
        self.q_stop = QPushButton(t("wg_q_stop"))
        self.q_stop.setObjectName("Link")
        self.q_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.q_stop.clicked.connect(self.stop_queue)
        qtop.addWidget(self.q_stop)
        ql.addLayout(qtop)
        self.q_bar = QProgressBar()
        self.q_bar.setTextVisible(False)
        self.q_bar.setRange(0, 1000)
        ql.addWidget(self.q_bar)
        self.q_next = QLabel()
        self.q_next.setObjectName("Muted")
        self.q_next.setWordWrap(True)
        ql.addWidget(self.q_next)
        lay.addWidget(self.q_card)

        self.wg_card = QFrame()
        self.wg_card.setObjectName("Card")
        self.wg_lay = QVBoxLayout(self.wg_card)
        self.wg_lay.setContentsMargins(0, 4, 0, 4)
        self.wg_lay.setSpacing(0)
        lay.addWidget(self.wg_card)
        hint = QLabel(t("wg_hint"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        hint.setContentsMargins(4, 2, 4, 0)
        lay.addWidget(hint)

        lay.addSpacing(18)
        store = QFrame()
        store.setObjectName("Card")
        sl = QHBoxLayout(store)
        sl.setContentsMargins(20, 14, 14, 14)
        sl.setSpacing(14)
        mid = QVBoxLayout()
        mid.setSpacing(1)
        nm = QLabel(t("store"))
        nm.setObjectName("RowName")
        mid.addWidget(nm)
        ds = QLabel(t("store_desc"))
        ds.setObjectName("Muted")
        ds.setWordWrap(True)
        mid.addWidget(ds)
        sl.addLayout(mid, 1)
        sb = QPushButton(t("store_open"))
        sb.setCursor(Qt.CursorShape.PointingHandCursor)
        sb.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(W.STORE_UPDATES)))
        sl.addWidget(sb)
        lay.addWidget(store)
        lay.addStretch(1)
        self._fill_other()

    # gizle / atla / önerilen
    def wg_hidden(self, x):
        return x["id"] in (prefs.get("wg_ignore") or []) or \
            (prefs.get("wg_skip") or {}).get(x["id"]) == x.get("available")

    def wg_visible(self):
        return [x for x in self.wg if not self.wg_hidden(x)]

    def _ordered(self):
        """Önerilenler başta, sonra adına göre; gizlenenler (gösteriliyorsa) en sonda."""
        vis = sorted(self.wg_visible(), key=lambda x: (not W.recommended(x["id"]), x["name"].lower()))
        hid = [x for x in self.wg if self.wg_hidden(x)] if self.wg_show_hidden else []
        return vis + hid

    def skip(self, pid, version):
        prefs.set("wg_skip", dict(prefs.get("wg_skip") or {}, **{pid: version}))
        self._fill_other()

    def ignore(self, pid):
        prefs.set("wg_ignore", sorted(set(prefs.get("wg_ignore") or []) | {pid}))
        self._fill_other()

    def unhide(self, pid):
        prefs.update({"wg_ignore": [x for x in (prefs.get("wg_ignore") or []) if x != pid],
                      "wg_skip": {k: v for k, v in (prefs.get("wg_skip") or {}).items() if k != pid}})
        self._fill_other()

    def _toggle_hidden(self):
        self.wg_show_hidden = not self.wg_show_hidden
        self._fill_other()

    # simge / boyut
    def pkg_icon(self, item):
        key = (item.get("icon") or "", item["name"])
        if key not in self._icons:
            self._icons[key] = pkg_pixmap(key[0], item["name"], 28, self.devicePixelRatioF())
        return self._icons[key]

    def wg_size_of(self, item):
        v = self.wg_sizes.get(item["id"])
        return v[1] if v and v[0] == item.get("available") else 0

    def _fetch_sizes(self):
        """Boyutu bilinmeyenlerin kurulum dosyası boyutu (winget show + HEAD), üçer üçer, arka planda."""
        todo = [(x["id"], x.get("available", "")) for x in self.wg
                if x["id"] not in self.wg_sizes or self.wg_sizes[x["id"]][0] != x.get("available")]
        if self._wg_sizing or not todo:
            return
        self._wg_sizing = True

        def work():
            with ThreadPoolExecutor(3) as ex:
                for (pid, ver), n in zip(todo, ex.map(lambda pv: W.size(pv[0]), todo)):
                    self.bus.wg_size.emit(pid, ver, n)
            self.bus.wg_size.emit("", "", 0)            # bitti
        threading.Thread(target=work, daemon=True).start()

    def _on_wg_size(self, pid, ver, n):
        if not pid:
            self._wg_sizing = False
            ids = {x["id"] for x in self.wg}
            prefs.set("wg_sizes", {k: v for k, v in self.wg_sizes.items() if k in ids})
            return
        self.wg_sizes[pid] = [ver, n]
        row = self.wg_rows.get(pid)
        try:
            if row:
                row.refresh()
            self._refresh_wg_status()
        except RuntimeError:
            pass

    def _fill_other(self):
        """Güncelleme satırlarını, durum yazısını, sırayı ve sekme sayacını yeniden kur."""
        try:
            while self.wg_lay.count():
                w = self.wg_lay.takeAt(0).widget()
                if w:
                    w.hide()                 # silinene kadar eski satır yenisinin üstünde çizilmesin
                    w.setParent(None)
                    w.deleteLater()
        except RuntimeError:
            return
        self.wg_rows = {}
        rows = self._ordered()
        for i, item in enumerate(rows):
            if i:
                d = QFrame()
                d.setObjectName("Divider")
                self.wg_lay.addWidget(d)
            row = WgRow(item, self)
            self.wg_rows[item["id"]] = row
            self.wg_lay.addWidget(row)
        self.wg_card.setVisible(bool(rows))
        self._refresh_wg_status()
        self._refresh_queue()
        self.btn_getwg.setVisible(self.wg_err == "missing")
        idle = [x for x in self.wg_visible() if x["id"] not in self.wg_jobs]
        self.btn_all.setVisible(len(idle) > 1)
        rec = [x for x in idle if W.recommended(x["id"])]
        self.btn_rec.setVisible(bool(rec) and len(rec) < len(idle))

    def _refresh_wg_status(self):
        vis = self.wg_visible()
        n, hidden = len(vis), len(self.wg) - len(vis)
        checked = float(prefs.get("wg_checked", 0) or 0)
        if self._wg_checking:
            msg = t("checking")
        elif self.wg_err == "missing":
            msg = t("wg_missing")
        elif self.wg_err:
            msg = t("wg_fail")
        elif not checked:
            msg = t("wg_never")
        else:
            parts = [t("wg_count", n=n) if n else t("wg_none")]
            nrec = sum(W.recommended(x["id"]) for x in vis)
            if nrec:
                parts.append(t("wg_rec_n", n=nrec))
            total = sum(self.wg_size_of(x) for x in vis)
            if total:
                parts.append(t("wg_total", s=fmt_size(total)))
            if self.wg_summary:
                parts.append(self.wg_summary)
            parts.append(t("wg_checked", t=ago(checked)))
            msg = "  ·  ".join(parts)
        self.wg_status.setText(msg)
        self.wg_status.setProperty("state", "new" if n and not self._wg_checking else "")
        self.wg_status.style().unpolish(self.wg_status)
        self.wg_status.style().polish(self.wg_status)
        self.btn_hidden.setVisible(bool(hidden))
        self.btn_hidden.setText(t("wg_hide_hidden") if self.wg_show_hidden else t("wg_show_hidden", n=hidden))
        self.tabs[1].setText(t("tab_other") + (f"  ·  {n}" if n else ""))

    def _refresh_queue(self):
        """Sıra kartı: şu an kurulan, kaçıncı, genel ilerleme, sıradakiler."""
        try:
            b = self.wg_batch
            if not self.wg_jobs or b["total"] < 1:
                self.q_card.hide()
                return
            names = {x["id"]: x["name"] for x in self.wg}
            cur = next((p for p, j in self.wg_jobs.items() if j["phase"] != "queued"), None)
            frac = 0.0
            if cur:
                j = self.wg_jobs[cur]
                frac = {"start": 0.02, "install": 0.85}.get(j["phase"], 0.0)
                if j["phase"] == "download":
                    frac = 0.8 * j["p"] / 100 if j.get("p", -1) >= 0 else 0.1
                self.q_title.setText(t("wg_q_now", a=names.get(cur, cur)))
            else:
                self.q_title.setText(t("wg_queued"))
            self.q_count.setText(t("wg_q_of", i=min(b["total"], b["done"] + 1), n=b["total"]))
            self.q_bar.setValue(int(1000 * (b["done"] + frac) / b["total"]))
            with self._wg_lock:
                q = list(self._wg_q)
            nxt = [names.get(p, p) for p in q[:4]]
            more = len(q) - len(nxt)
            self.q_next.setText(t("wg_q_next", a=", ".join(nxt) + (f"  +{more}" if more > 0 else "")) if q else "")
            self.q_next.setVisible(bool(q))
            self.q_stop.setVisible(bool(q))
            self.q_card.show()
        except RuntimeError:
            pass

    def queue_pos(self, pid):
        with self._wg_lock:
            return self._wg_q.index(pid) + 1 if pid in self._wg_q else 0

    def check_other(self):
        if self._wg_checking:
            return
        self._wg_checking = True
        self._refresh_check_btn()
        self._fill_other()
        threading.Thread(target=lambda: self.bus.wg_list.emit(*W.list_upgrades()), daemon=True).start()

    def _on_wg_list(self, rows, err):
        self._wg_checking = False
        self.wg_err = err
        if not err or err == "missing":
            ids = {r["id"] for r in rows}
            keep = [x for x in self.wg if x["id"] in self.wg_jobs and x["id"] not in ids]
            self.wg = rows + keep
            self.wg_failed &= ids
            self.wg_summary = ""
            avail = {r["id"]: r.get("available") for r in rows}
            prefs.update({"wg_upgrades": self.wg, "wg_checked": 0 if err else time.time(),
                          # yeni sürüm gelince "bu sürümü atla" kendiliğinden düşer
                          "wg_skip": {k: v for k, v in (prefs.get("wg_skip") or {}).items() if avail.get(k) == v}})
        self._refresh_check_btn()
        self._fill_other()
        self._fetch_sizes()

    # sırayla güncelleme
    def update_pkg(self, pid):
        if pid in self.wg_jobs:
            return
        if not self.wg_jobs:
            self.wg_batch = {"total": 0, "done": 0, "ok": 0, "fail": 0}
            self.wg_summary = ""
        self.wg_batch["total"] += 1
        self.wg_failed.discard(pid)
        self.wg_jobs[pid] = {"phase": "queued", "p": -1}
        with self._wg_lock:
            self._wg_q.append(pid)
            start = not self._wg_worker
            self._wg_worker = True
        if start:
            threading.Thread(target=self._wg_work, daemon=True).start()
        self._fill_other()

    def update_all(self):
        for x in self._ordered():
            if not self.wg_hidden(x):
                self.update_pkg(x["id"])

    def update_recommended(self):
        for x in self._ordered():
            if not self.wg_hidden(x) and W.recommended(x["id"]):
                self.update_pkg(x["id"])

    def dequeue(self, pid):
        with self._wg_lock:
            if pid not in self._wg_q:
                return                      # başlamış
            self._wg_q.remove(pid)
        self.wg_jobs.pop(pid, None)
        self.wg_batch["total"] -= 1
        self._fill_other()

    def stop_queue(self):
        """Sıradakileri bırak; şu an kurulan biter."""
        with self._wg_lock:
            q, self._wg_q[:] = list(self._wg_q), []
        for pid in q:
            self.wg_jobs.pop(pid, None)
        self.wg_batch["total"] -= len(q)
        self._fill_other()

    def _wg_work(self):
        """Paketleri sırayla güncelle (winget aynı anda iki kurulumu sevmez)."""
        while True:
            with self._wg_lock:
                if not self._wg_q:
                    self._wg_worker = False
                    return
                pid = self._wg_q.pop(0)
            self.bus.wg_phase.emit(pid, "start")
            self.bus.wg_done.emit(pid, W.upgrade(pid, lambda ph, pid=pid: self.bus.wg_phase.emit(pid, ph)))

    def _on_wg_phase(self, pid, phase):
        job = self.wg_jobs.get(pid)
        if not job:
            return
        first = job["phase"] == "queued"
        job.update(phase=phase, p=-1, got=0)
        if phase == "download":
            self._wg_tick_once(pid)
        if phase in ("start", "download"):
            self.wg_tick.start(400)
        else:
            self.wg_tick.stop()
        if first:
            self._fill_other()          # sıra numaraları kaydı
        else:
            self._refresh_row(pid)

    def _wg_tick(self):
        cur = next((p for p, j in self.wg_jobs.items() if j["phase"] == "download"), None)
        if cur:
            self._wg_tick_once(cur)
            self._refresh_row(cur)

    def _wg_tick_once(self, pid):
        """İndirme ilerlemesi: winget'in geçici klasöründeki dosyanın boyutu / kurulum dosyasının boyutu."""
        job = self.wg_jobs.get(pid)
        item = next((x for x in self.wg if x["id"] == pid), None)
        if not job or not item:
            return
        got = W.staged_bytes(pid)
        total = self.wg_size_of(item)
        job["got"] = got
        job["p"] = min(99, int(got * 100 / total)) if total and got else -1

    def _refresh_row(self, pid):
        row = self.wg_rows.get(pid)
        try:
            if row:
                row.refresh()
        except RuntimeError:
            pass
        self._refresh_queue()

    def _on_wg_done(self, pid, code):
        self.wg_jobs.pop(pid, None)
        if not any(j["phase"] in ("start", "download") for j in self.wg_jobs.values()):
            self.wg_tick.stop()
        b = self.wg_batch
        b["done"] += 1
        if code in WG_OK:
            b["ok"] += 1
            self.wg = [x for x in self.wg if x["id"] != pid]
            prefs.set("wg_upgrades", self.wg)
        else:
            b["fail"] += 1
            self.wg_failed.add(pid)
        if not self.wg_jobs and b["total"] > 1:
            s = [t("wg_done_ok", n=b["ok"])] if b["ok"] else []
            if b["fail"]:
                s.append(t("wg_done_fail", n=b["fail"]))
            self.wg_summary = ", ".join(s)
        self._fill_other()

    def _settings_card(self):
        card = QFrame()
        card.setObjectName("Card")
        g = QGridLayout(card)
        g.setContentsMargins(20, 18, 20, 18)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(14)
        g.setColumnStretch(1, 1)

        def label(text):
            lb = QLabel(text)
            lb.setObjectName("Muted")
            lb.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            lb.setContentsMargins(0, 6, 0, 0)
            return lb

        cur = theme.current_variant()
        self.theme_group = QButtonGroup(card)
        tbox = QVBoxLayout()
        tbox.setSpacing(4)
        for fam in ("dark", "light"):
            row = QHBoxLayout()
            row.setSpacing(6)
            for vid, v in VARIANTS.items():
                if v[2] != fam:
                    continue
                sw = VariantSwatch(vid)
                sw.setChecked(vid == cur)
                sw.clicked.connect(lambda _c=False, vid=vid: self.set_shared(theme=vid))
                self.theme_group.addButton(sw)
                row.addWidget(sw)
            row.addStretch(1)
            tbox.addLayout(row)
        g.addWidget(label(t("theme")), 0, 0)
        g.addLayout(tbox, 0, 1)

        arow = QHBoxLayout()
        arow.setSpacing(4)
        acc = prefs.get("accent", "gray")
        grp = QButtonGroup(card)
        for key in ACCENTS:
            sw = AccentSwatch(key)
            sw.setChecked(key == acc)
            sw.clicked.connect(lambda _c=False, key=key: self.set_shared(accent=key))
            grp.addButton(sw)
            arow.addWidget(sw)
        arow.addStretch(1)
        g.addWidget(label(t("accent")), 1, 0)
        g.addLayout(arow, 1, 1)

        lrow = QHBoxLayout()
        lrow.setSpacing(6)
        lgrp = QButtonGroup(card)
        for code, text in (("tr", "Türkçe"), ("en", "English")):
            b = QPushButton(text)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setChecked(prefs.get("language", "tr") == code)
            b.clicked.connect(lambda _c=False, code=code: self.set_shared(language=code))
            lgrp.addButton(b)
            lrow.addWidget(b)
        lrow.addStretch(1)
        g.addWidget(label(t("language")), 2, 0)
        g.addLayout(lrow, 2, 1)

        srow = QHBoxLayout()
        srow.setSpacing(6)
        sel = set(prefs.get("sync_apps") or [])
        for a in A.APPS:
            if not a.shares_theme:
                continue
            cb = QPushButton(a.name)
            cb.setObjectName("Chip")
            cb.setCheckable(True)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setChecked(a.id in sel)
            cb.toggled.connect(lambda on, aid=a.id: self._toggle_sync(aid, on))
            srow.addWidget(cb)
        srow.addStretch(1)
        g.addWidget(label(t("apply_to")), 3, 0)
        g.addLayout(srow, 3, 1)

        self.status = QLabel(self._status_msg)
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.setVisible(bool(self._status_msg))
        g.addWidget(self.status, 5, 1)
        return card

    def _dark_titlebar(self):
        try:
            import ctypes
            val = ctypes.c_int(1 if theme.is_dark() else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(val), 4)
        except Exception:
            pass

    # -- ortak ayarlar
    def set_shared(self, **kw):
        lang_before = prefs.get("language")
        v = shared.values()
        v.update(kw)
        prefs.update(shared.normalize(v))
        res = shared.apply_all(running=self.running)
        ok = [A.BY_ID[k].name for k, s in res.items() if s in ("ok", "same")]
        miss = [A.BY_ID[k].name for k, s in res.items() if s == "missing"]
        later = [A.BY_ID[k].name for k, s in res.items() if s == "running"]
        msg = t("applied", a=", ".join(ok)) + " " + t("applied_live") if ok else t("applied_none")
        if later:
            msg += "\n" + t("applied_later", a=", ".join(later))
        if miss:
            msg += "\n" + t("not_found", a=", ".join(miss))
        self._status_msg = msg
        if prefs.get("language") != lang_before or "theme" in kw or "accent" in kw:
            self.build()                   # tamga'nın kendisi de değişsin
        else:
            self.status.setText(msg)
            self.status.setVisible(True)

    def _toggle_sync(self, aid, on):
        sel = [x for x in (prefs.get("sync_apps") or []) if x != aid]
        if on:
            sel.append(aid)
        prefs.set("sync_apps", sel)
        if on:
            shared.apply_to(A.BY_ID[aid])

    # -- aç
    def launch(self, aid):
        inst = self.inst.get(aid)
        if not inst:
            return
        app = A.BY_ID[aid]
        if app.shares_theme and aid in (prefs.get("sync_apps") or []) and aid not in self.running:
            shared.apply_to(app)
        try:
            subprocess.Popen([inst.exe], cwd=inst.location, close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x8))
        except OSError:
            os.startfile(inst.exe)

    # -- güncelleme denetimi
    def check_updates(self, force=False):
        if self._checking:
            return
        self._checking = True
        self._refresh_check_btn()

        def work():
            self.bus.release.emit(SELF, github.latest(REPO))
            for a in A.APPS:
                self.bus.release.emit(a.id, github.latest(a.repo))
            self.bus.check_done.emit()
        threading.Thread(target=work, daemon=True).start()

    def _on_release(self, aid, info):
        if info.get("error") in ("net", "rate") and self.rel.get(aid, {}).get("version"):
            info = dict(self.rel[aid], error=info["error"])     # eski bilgiyi koru
        self.rel[aid] = info
        if aid == SELF:
            self._refresh_self()
        elif aid in self.cards:
            self.cards[aid].refresh()

    def _on_check_done(self):
        self._checking = False
        prefs.update({"releases": {k: {x: y for x, y in v.items() if x != "error" or y == "none"}
                                   for k, v in self.rel.items()},
                      "releases_checked": time.time()})
        self._refresh_check_btn()

    # -- indir + kur
    def install(self, aid):
        rel = self.rel.get(aid) or {}
        url = rel.get("asset_url")
        if not url or aid in self.jobs:
            return
        if aid in self.running:
            box = QMessageBox(QMessageBox.Icon.NoIcon, "tamga", t("update_close", a=A.BY_ID[aid].name),
                              QMessageBox.StandardButton.NoButton, self)
            ok = box.addButton(t("continue"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(t("cancel"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not ok:
                return
        name = os.path.basename(rel.get("asset_name") or f"{aid}-setup.exe")
        dest = os.path.join(DOWNLOAD_DIR, name)
        self.jobs[aid] = {"phase": "download", "p": -1}
        self.cards[aid].refresh()

        def work():
            last = [0.0]

            def prog(got, total):
                now = time.monotonic()
                if now - last[0] > 0.1 or got == total:
                    last[0] = now
                    self.bus.progress.emit(aid, got, total)
            try:
                github.download(url, dest, prog, cancelled=lambda: aid in self._cancel)
                self.bus.downloaded.emit(aid, dest)
            except Exception as e:
                self.bus.failed.emit(aid, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, aid, got, total):
        job = self.jobs.get(aid)
        if job:
            job["p"] = int(got * 1000 / total) if total else -1
            if aid == SELF:
                self._refresh_self()
            else:
                self.cards[aid].refresh()

    # -- tamga'nın kendisi
    def _self_newer(self):
        rv = (self.rel.get(SELF) or {}).get("version", "")
        return rv if rv and A.is_newer(rv, __version__) else ""

    def _refresh_self(self):
        """Başlıkta sürüm numarası; yeni sürüm varsa yanında Güncelle düğmesi."""
        try:
            rv, job = self._self_newer(), self.jobs.get(SELF)
            err = (self.rel.get(SELF) or {}).get("error")
            extra = t("new_v", v=rv) if rv else t("rate_error") if err == "rate" else t("net_error") if err == "net" else ""
            self.lbl_ver.setText(__version__ + ("  ·  " + extra if extra else ""))
            self.lbl_ver.setProperty("state", "new" if rv else "")
            self.lbl_ver.style().unpolish(self.lbl_ver)
            self.lbl_ver.style().polish(self.lbl_ver)
            can = bool(rv and (self.rel.get(SELF) or {}).get("asset_url"))
            self.btn_self.setVisible(can or bool(job))
            self.btn_self.setEnabled(not job)
            self.btn_self_notes.setVisible(bool(rv and (self.rel.get(SELF) or {}).get("notes")) and not job)
            if job and job["phase"] == "download":
                pct = f"%{job['p'] // 10}" if is_tr() else f"{job['p'] // 10}%"
                self.btn_self.setText(t("downloading", p=pct if job["p"] >= 0 else ""))
            elif job:
                self.btn_self.setText(t("installing"))
            else:
                self.btn_self.setText(t("update"))
        except RuntimeError:          # pencere yeniden kuruluyor
            pass

    def _self_notes(self):
        rel = self.rel.get(SELF) or {}
        box = QMessageBox(QMessageBox.Icon.NoIcon, f"tamga {rel.get('version', '')}", rel.get("notes", ""),
                          QMessageBox.StandardButton.Close, self)
        box.setTextFormat(Qt.TextFormat.MarkdownText)
        box.exec()

    def update_self(self):
        """Yeni tamga kurulumunu indir, sessizce kur; tamga kapanır, kurulum bitince yeniden açılır."""
        rel = self.rel.get(SELF) or {}
        url = rel.get("asset_url")
        if not url or SELF in self.jobs:
            return
        dest = os.path.join(DOWNLOAD_DIR, os.path.basename(rel.get("asset_name") or "tamga-setup.exe"))
        self.jobs[SELF] = {"phase": "download", "p": -1}
        self._refresh_self()

        def work():
            try:
                github.download(url, dest, lambda g, n: self.bus.progress.emit(SELF, g, n))
                self.bus.downloaded.emit(SELF, dest)
            except Exception as e:
                self.bus.failed.emit(SELF, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _clean_downloads(self):
        """Önceki kendini güncellemeden kalan kurulum dosyaları."""
        try:
            for n in os.listdir(DOWNLOAD_DIR):
                if n.lower().startswith("tamga") and n.lower().endswith((".exe", ".part")):
                    os.remove(os.path.join(DOWNLOAD_DIR, n))
        except OSError:
            pass

    def _on_downloaded(self, aid, path):
        if aid == SELF:
            # /relaunch=1: kurulum bitince tamga'yı yeniden açar (installer.iss [Run])
            args = [path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/relaunch=1"]
            try:
                subprocess.Popen(args, close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x8))
            except OSError as e:
                self._on_failed(aid, str(e))
                return
            self.jobs[SELF] = {"phase": "install", "p": 1000}
            self._refresh_self()
            QTimer.singleShot(400, QApplication.instance().quit)   # dosyalar kilitli kalmasın
            return
        # Inno Setup: sihirbazsız, ilerleme penceresiyle; açık uygulamayı kapatıp sonra yeniden açar
        args = [path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
        try:
            self._procs[aid] = (subprocess.Popen(args), path)
        except OSError as e:
            self._on_failed(aid, str(e))
            return
        self.jobs[aid] = {"phase": "install", "p": 1000}
        self.cards[aid].refresh()

    def _check_installers(self):
        for aid, (proc, path) in list(self._procs.items()):
            code = proc.poll()
            if code is None:
                continue
            del self._procs[aid]
            self.jobs.pop(aid, None)
            try:
                os.remove(path)
            except OSError:
                pass
            if code != 0:
                self._show_card_error(aid, t("inst_failed"))
            elif A.BY_ID[aid].shares_theme and aid in (prefs.get("sync_apps") or []):
                shared.apply_to(A.BY_ID[aid])
            self.cards[aid].refresh()

    def _on_failed(self, aid, _msg):
        self.jobs.pop(aid, None)
        self._cancel.discard(aid)
        if aid == SELF:
            self._refresh_self()
            self.lbl_ver.setText(self.lbl_ver.text() + "  ·  " + t("dl_failed"))
            return
        self.cards[aid].refresh()
        self._show_card_error(aid, t("dl_failed"))

    def _show_card_error(self, aid, text):
        st = self.cards[aid].status
        st.setText(st.text() + "  ·  " + text)

    def closeEvent(self, e):
        g = self.geometry()
        prefs.set("window_geometry", [g.x(), g.y(), g.width(), g.height()])
        super().closeEvent(e)

    def sizeHint(self):
        return QSize(780, 860)

