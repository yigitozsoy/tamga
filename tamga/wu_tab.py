"""Windows sekmesi: Windows Update'teki bekleyen güncellemeler; seç, kur (tek yönetici izni), gizle."""
import threading
import time

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from . import winupdate as U
from .config import prefs
from .i18n import t

CHECK_EVERY = 6 * 3600      # arama yarım dakika sürüyor: kendiliğinden en fazla 6 saatte bir


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


class WuRow(QWidget):
    def __init__(self, u, page):
        super().__init__()
        from .window import fmt_size
        self.u, self.page = u, page
        uid = u["id"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 14, 10)
        lay.setSpacing(14)
        self.cb = QCheckBox()
        self.cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cb.setChecked(uid in page.sel)
        self.cb.setVisible(not u.get("hidden"))
        self.cb.setEnabled(not page.busy())
        self.cb.toggled.connect(lambda on: page.select(uid, on))
        lay.addWidget(self.cb, 0, Qt.AlignmentFlag.AlignTop)
        mid = QVBoxLayout()
        mid.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(u.get("title") or uid)
        name.setObjectName("RowName")
        name.setWordWrap(True)
        name.setToolTip((u.get("desc") or "").strip())
        top.addWidget(name, 1)
        if U.important(u):
            badge = QLabel(t("wu_important"))
            badge.setObjectName("Badge")
            top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        mid.addLayout(top)
        parts = [t("wu_kind_" + u["kind"])]
        if u.get("kb"):
            parts.append("KB" + u["kb"].split(",")[0])
        sz = fmt_size(u.get("size") or 0)
        if sz and u["kind"] != "definition":            # tanımlarda en büyük boyut gerçeği yansıtmıyor (GB'lar)
            parts.append(t("wu_max", s=sz))
        if u.get("optional"):
            parts.append(t("wu_optional"))
        state = ""
        if u.get("hidden"):
            parts.append(t("wg_ignored"))
        elif uid in page.failed:
            parts.append(t("wu_failed"))
            state = "err"
        st = QLabel("  ·  ".join(parts))
        st.setObjectName("Status")
        st.setWordWrap(True)
        st.setProperty("state", state)
        if uid in page.failed:
            st.setToolTip(t("wg_code_tip", c=f"0x{page.failed[uid] & 0xFFFFFFFF:08X}"))
        elif u["kind"] == "driver":
            st.setToolTip(t("wu_driver_tip"))
        mid.addWidget(st)
        lay.addLayout(mid, 1)
        self.btn = QPushButton(t("wg_unhide") if u.get("hidden") else t("wg_hide"))
        self.btn.setObjectName("Link")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setToolTip("" if u.get("hidden") else t("wu_hide_tip"))
        self.btn.setEnabled(not page.busy() and uid not in page.hiding)
        self.btn.clicked.connect(lambda: page.hide(uid, not u.get("hidden")))
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignTop)


class WuPage(QObject):
    searched = pyqtSignal(list, bool, int)
    hid = pyqtSignal(list, bool, int)

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.ups = [u for u in (prefs.get("wu_updates") or []) if isinstance(u, dict) and u.get("id")]
        for u in self.ups:
            u["kind"] = U.kind(u)
        self.reboot = bool(prefs.get("wu_reboot"))
        self.sel = {u["id"] for u in self.ups if U.default_selected(u)}
        self.err = 0
        self.checking = False
        self.show_hidden = False
        self.failed = {}            # kimlik -> HRESULT
        self.hiding = set()
        self.summary = ""
        self.job = None             # kurulum sürerken son durum
        self.inst = U.Installer()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.searched.connect(self._on_search)
        self.hid.connect(self._on_hidden)

    def busy(self):
        return self.job is not None

    def due(self):
        return time.time() - float(prefs.get("wu_checked", 0) or 0) > CHECK_EVERY

    def visible(self):
        return [u for u in self.ups if not u.get("hidden")]

    # -- arayüz
    def build(self, lay):
        hrow = QHBoxLayout()
        hrow.setSpacing(8)
        hrow.addWidget(self.win._section(t("wu_title")))
        hrow.addStretch(1)
        self.btn_install = QPushButton()
        self.btn_install.setObjectName("Primary")
        self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install.setToolTip(t("wu_install_tip"))
        self.btn_install.clicked.connect(self.install)
        hrow.addWidget(self.btn_install, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(hrow)

        srow = QHBoxLayout()
        srow.setContentsMargins(4, 0, 0, 0)
        self.status = QLabel()
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        srow.addWidget(self.status, 1)
        self.btn_hidden = QPushButton()
        self.btn_hidden.setObjectName("Link")
        self.btn_hidden.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hidden.clicked.connect(self._toggle_hidden)
        srow.addWidget(self.btn_hidden)
        b = QPushButton(t("wu_open"))
        b.setObjectName("Link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(U.SETTINGS)))
        srow.addWidget(b)
        lay.addLayout(srow)

        # yeniden başlatma bekliyor
        self.rb_card = QFrame()
        self.rb_card.setObjectName("Card")
        rl = QHBoxLayout(self.rb_card)
        rl.setContentsMargins(20, 14, 14, 14)
        rl.setSpacing(14)
        rt = QLabel(t("wu_reboot"))
        rt.setObjectName("RowName")
        rt.setWordWrap(True)
        rl.addWidget(rt, 1)
        rb = QPushButton(t("wu_restart"))
        rb.setCursor(Qt.CursorShape.PointingHandCursor)
        rb.clicked.connect(self.restart)
        rl.addWidget(rb)
        lay.addWidget(self.rb_card)

        # kurulum ilerlemesi
        self.p_card = QFrame()
        self.p_card.setObjectName("Card")
        pl = QVBoxLayout(self.p_card)
        pl.setContentsMargins(20, 14, 14, 14)
        pl.setSpacing(6)
        ptop = QHBoxLayout()
        self.p_title = QLabel()
        self.p_title.setObjectName("RowName")
        self.p_title.setWordWrap(True)
        ptop.addWidget(self.p_title, 1)
        self.p_count = QLabel()
        self.p_count.setObjectName("Status")
        ptop.addWidget(self.p_count, 0, Qt.AlignmentFlag.AlignTop)
        pl.addLayout(ptop)
        self.p_bar = QProgressBar()
        self.p_bar.setTextVisible(False)
        pl.addWidget(self.p_bar)
        lay.addWidget(self.p_card)

        self.card = QFrame()
        self.card.setObjectName("Card")
        self.lst = QVBoxLayout(self.card)
        self.lst.setContentsMargins(0, 4, 0, 4)
        self.lst.setSpacing(0)
        lay.addWidget(self.card)
        hint = QLabel(t("wu_hint"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        hint.setContentsMargins(4, 2, 4, 0)
        lay.addWidget(hint)
        lay.addStretch(1)
        self.fill()

    def fill(self):
        try:
            while self.lst.count():
                w = self.lst.takeAt(0).widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
        except RuntimeError:
            return
        vis = self.visible()
        # önemliler başta, sonra seçili olanlar, sonra ada göre; gizlenenler (gösteriliyorsa) en sonda
        rows = sorted(vis, key=lambda u: (not U.important(u), u["id"] not in self.sel, (u.get("title") or "").lower()))
        if self.show_hidden:
            rows += [u for u in self.ups if u.get("hidden")]
        self.rows = {}
        for i, u in enumerate(rows):
            if i:
                d = QFrame()
                d.setObjectName("Divider")
                self.lst.addWidget(d)
            r = WuRow(u, self)
            self.rows[u["id"]] = r
            self.lst.addWidget(r)
        self.card.setVisible(bool(rows))
        self.refresh()

    def refresh(self):
        """Durum yazısı, düğmeler, ilerleme kartı, sekme sayacı."""
        from .window import ago
        try:
            vis = self.visible()
            n, hidden = len(vis), len(self.ups) - len(vis)
            checked = float(prefs.get("wu_checked", 0) or 0)
            if self.checking:
                msg = t("wu_searching")
            elif self.err:
                msg = t("wu_fail", c=f"0x{self.err & 0xFFFFFFFF:08X}")
            elif not checked:
                msg = t("wg_never")
            else:
                parts = [t("wg_count", n=n) if n else t("wg_none")]
                if self.summary:
                    parts.append(self.summary)
                parts.append(t("wg_checked", t=ago(checked)))
                msg = "  ·  ".join(parts)
            self.status.setText(msg)
            self.status.setProperty("state", "new" if n and not self.checking else "")
            _repolish(self.status)
            self.btn_hidden.setVisible(bool(hidden))
            self.btn_hidden.setText(t("wg_hide_hidden") if self.show_hidden else t("wg_show_hidden", n=hidden))
            nsel = len([u for u in vis if u["id"] in self.sel])
            self.btn_install.setText(t("wu_install_sel", n=nsel))
            self.btn_install.setVisible(bool(vis) and not self.busy())
            self.btn_install.setEnabled(nsel > 0 and not self.checking)
            self.rb_card.setVisible(self.reboot and not self.busy())
            self._refresh_progress()
            self.win.tabs[2].setText(t("tab_windows") + (f"  ·  {n}" if n else ""))
        except (RuntimeError, AttributeError):
            pass

    def _refresh_progress(self):
        j = self.job
        if j is None:
            self.p_card.hide()
            return
        titles = {u["id"]: u.get("title") or u["id"] for u in self.ups}
        ph = j.get("phase")
        a = titles.get(j.get("id"), "")
        if ph == "download":
            self.p_title.setText(t("wu_downloading", a=a))
        elif ph == "install":
            self.p_title.setText(t("wu_installing", a=a))
        else:
            self.p_title.setText(t("wu_preparing"))
        i, n = int(j.get("i") or 0), int(j.get("n") or 0)
        self.p_count.setText(t("wg_q_of", i=i, n=n) if n else "")
        if n:
            self.p_bar.setRange(0, 100 * n)
            self.p_bar.setValue(100 * (i - 1) + (50 if ph == "install" else 10))
        else:
            self.p_bar.setRange(0, 0)
        self.p_card.show()

    # -- işler
    def select(self, uid, on):
        (self.sel.add if on else self.sel.discard)(uid)
        self.refresh()

    def _toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.fill()

    def check(self):
        if self.checking or self.busy():
            return
        self.checking = True
        self.win._refresh_check_btn()
        self.refresh()
        threading.Thread(target=lambda: self.searched.emit(*U.search()), daemon=True).start()

    def _on_search(self, ups, reboot, err):
        self.checking = False
        self.err = err
        if not err:
            old = {u["id"] for u in self.ups}
            ids = {u["id"] for u in ups}
            # yeni gelenler varsayılana göre; önceden bilinenlerde kullanıcının seçimi kalır
            self.sel = (self.sel & ids) | {u["id"] for u in ups if u["id"] not in old and U.default_selected(u)}
            self.ups = ups
            self.reboot = reboot
            self.failed = {k: v for k, v in self.failed.items() if k in ids}
            self.summary = ""
            prefs.update({"wu_updates": ups, "wu_reboot": reboot, "wu_checked": time.time()})
        self.win._refresh_check_btn()
        self.fill()

    def install(self):
        ids = [u["id"] for u in self.visible() if u["id"] in self.sel]
        if not ids or self.busy():
            return
        err = self.inst.start(ids)
        if err:
            self.summary = t("wg_err_denied") if err == 1223 else t("wu_fail", c=f"0x{err & 0xFFFFFFFF:08X}")
            self.refresh()
            return
        self.summary = ""
        self.job = {"phase": "start", "ids": ids}
        self.timer.start(700)
        self.fill()

    def _tick(self):
        st = self.inst.poll()
        if isinstance(st, dict):
            self.job = dict(st, ids=self.job.get("ids", []))
        done = isinstance(st, dict) and st.get("phase") in ("done", "error")
        if done or not self.inst.running():
            self._finish(st if isinstance(st, dict) else None)
        else:
            self.refresh()

    def _finish(self, st):
        self.timer.stop()
        ids = (self.job or {}).get("ids", [])
        self.inst.close()
        self.job = None
        res = (st or {}).get("results") or {}
        ok = [k for k, v in res.items() if isinstance(v, dict) and v.get("code") in U.OK_CODES]
        bad = {k: int(v.get("hr") or 0) for k, v in res.items() if k not in ok and isinstance(v, dict)}
        if st is None or st.get("phase") == "error":
            for k in ids:
                if k not in res:
                    bad[k] = int((st or {}).get("hr") or -1)
        self.failed.update(bad)
        self.ups = [u for u in self.ups if u["id"] not in ok]
        self.sel -= set(ok)
        if (st or {}).get("reboot"):
            self.reboot = True
        s = [t("wu_done_ok", n=len(ok))] if ok else []
        if bad:
            s.append(t("wu_done_fail", n=len(bad)))
        self.summary = ", ".join(s)
        prefs.update({"wu_updates": self.ups, "wu_reboot": self.reboot})
        self.fill()

    def hide(self, uid, hidden):
        if uid in self.hiding or self.busy():
            return
        self.hiding.add(uid)
        self.fill()
        threading.Thread(target=lambda: self.hid.emit([uid], hidden, U.set_hidden([uid], hidden)), daemon=True).start()

    def _on_hidden(self, ids, hidden, code):
        self.hiding -= set(ids)
        if code == 0:
            for u in self.ups:
                if u["id"] in ids:
                    u["hidden"] = hidden
            if hidden:
                self.sel -= set(ids)
            prefs.set("wu_updates", self.ups)
            self.summary = ""
        else:
            self.summary = t("wg_err_denied") if code == 1223 else t("wu_hide_fail")
        self.fill()

    def restart(self):
        r = QMessageBox.question(self.win, t("wu_restart"), t("wu_restart_q"))
        if r == QMessageBox.StandardButton.Yes:
            U.restart()
