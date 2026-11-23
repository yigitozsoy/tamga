"""Ana pencere: uygulama kartları (kur / aç / güncelle) ve ortak ayarlar."""
import os
import subprocess
import threading
import time

from PyQt6.QtCore import QObject, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from . import REPO, __version__
from . import apps as A
from . import github, shared, theme
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
        lay.addWidget(self.logo)

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
        lay.addLayout(mid, 1)

        self.btn_page = QPushButton(t("releases_page"))
        self.btn_page.setObjectName("Link")
        self.btn_page.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl((self.win.rel.get(app.id) or {}).get("page") or f"https://github.com/{app.repo}/releases")))
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

    def refresh(self):
        w, aid = self.win, self.app.id
        inst, rel, job = w.inst.get(aid), w.rel.get(aid) or {}, w.jobs.get(aid)
        parts, state = [], ""
        rv = rel.get("version", "")
        if inst:
            parts.append(t("installed_v", v=inst.version or "?"))
            if rv and A.is_newer(rv, inst.version):
                parts.append(t("new_v", v=rv))
                state = "new"
            elif rv:
                parts.append(t("up_to_date"))
            if aid in w.running:
                parts.append(t("running"))
        else:
            parts.append(t("not_installed"))
            if rv:
                parts.append(t("latest_v", v=rv))
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
        self.btn_page.setVisible(bool(rel.get("page")) and not job)
        self.btn_open.setVisible(bool(inst))
        self.btn_open.setEnabled(not job)


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
        self.inst, self.running, self.jobs, self.cards = {}, set(), {}, {}
        self.rel = dict(prefs.get("releases") or {})
        self._checking = False
        self._procs = {}
        self._cancel = set()
        self._status_msg = ""

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
        if time.time() - float(prefs.get("releases_checked", 0) or 0) > CHECK_EVERY:
            QTimer.singleShot(300, self.check_updates)

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

    def refresh_cards(self):
        for c in self.cards.values():
            c.refresh()

    # -- arayüz
    def build(self):
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self._dark_titlebar()
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("Scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 32)
        lay.setSpacing(10)

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
        head.addStretch(1)
        self.btn_check = QPushButton(t("checking") if self._checking else t("check"))
        self.btn_check.setEnabled(not self._checking)
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.clicked.connect(lambda: self.check_updates(force=True))
        head.addWidget(self.btn_check)
        lay.addLayout(head)
        lay.addSpacing(14)

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
        self._refresh_self()
        old = self.centralWidget()
        self.setCentralWidget(root)
        if old:
            old.deleteLater()

    def _section(self, text):
        lb = QLabel(text)
        lb.setObjectName("Section")
        lb.setContentsMargins(4, 0, 0, 4)
        return lb

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
        self.btn_check.setEnabled(False)
        self.btn_check.setText(t("checking"))

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
        try:
            self.btn_check.setEnabled(True)
            self.btn_check.setText(t("check"))
        except RuntimeError:
            pass

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
            self.lbl_ver.setText(__version__ + ("  ·  " + t("new_v", v=rv) if rv else ""))
            self.lbl_ver.setProperty("state", "new" if rv else "")
            self.lbl_ver.style().unpolish(self.lbl_ver)
            self.lbl_ver.style().polish(self.lbl_ver)
            can = bool(rv and (self.rel.get(SELF) or {}).get("asset_url"))
            self.btn_self.setVisible(can or bool(job))
            self.btn_self.setEnabled(not job)
            if job and job["phase"] == "download":
                pct = f"%{job['p'] // 10}" if is_tr() else f"{job['p'] // 10}%"
                self.btn_self.setText(t("downloading", p=pct if job["p"] >= 0 else ""))
            elif job:
                self.btn_self.setText(t("installing"))
            else:
                self.btn_self.setText(t("update"))
        except RuntimeError:          # pencere yeniden kuruluyor
            pass

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

