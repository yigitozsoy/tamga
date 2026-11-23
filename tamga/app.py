"""Giriş: tek örnek (ikinci açılış var olan pencereyi öne getirir)."""
import ctypes
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

SERVER_NAME = "tamga-launcher-" + (os.environ.get("USERNAME") or "user")


def _already_running():
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show\n")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tamga.launcher")
    except Exception:
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("tamga")
    app.setQuitOnLastWindowClosed(True)
    if _already_running():
        return 0

    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    from .window import MainWindow
    win = MainWindow()
    win.show()

    def on_conn():
        s = server.nextPendingConnection()
        if s is None:
            return

        def read():
            if b"show" in bytes(s.readAll()):
                if win.isMinimized():
                    win.showNormal()
                win.show()
                win.raise_()
                win.activateWindow()
        s.readyRead.connect(read)
    server.newConnection.connect(on_conn)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
