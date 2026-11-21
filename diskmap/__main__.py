"""Desktop entry point, also used for the frozen package smoke test."""
import sqlite3
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .store import initialize
from .style import STYLE
from .ui import Window


def main():
    smoke = "--smoke" in sys.argv
    app = QApplication(sys.argv)
    app.setOrganizationName("Franklin Martins")
    app.setApplicationName("DiskMap Studio")
    app.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "icon.png")))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    storage = (tempfile.TemporaryDirectory(prefix="diskmap-smoke-") if smoke else
               nullcontext(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)))
    with storage as folder:
        database = Path(folder) / "index.sqlite3"
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(None, "DiskMap Studio", str(error))
            return 1
        lock = QLockFile(str(database.with_suffix(".lock")))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            QMessageBox.warning(None, "DiskMap Studio", "Outra instância está usando o histórico local.")
            return 1
        try:
            try:
                initialize(database)
            except (OSError, sqlite3.Error) as error:
                QMessageBox.critical(None, "DiskMap Studio", str(error))
                return 1
            window = Window(database)
            window.show()
            if smoke:
                QTimer.singleShot(220, window.close)
            return app.exec()
        finally:
            lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
