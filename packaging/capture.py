"""Generate the landing page image from the real Qt interface and sparse demo files."""
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from diskmap.store import initialize
from diskmap.style import STYLE
from diskmap.ui import Window

MIB = 1024 ** 2
FIXTURE = {
    "Vídeos/Documentário/Entrevistas.mov": 6450,
    "Vídeos/Documentário/Cenas externas.mov": 2360,
    "Vídeos/Estúdio/Tomadas de apoio.mp4": 1320,
    "Projetos/Catálogo 2026/Render final.mkv": 3180,
    "Projetos/Catálogo 2026/Edição.drp": 1030,
    "Base de mídia/Gravações.flac": 1710,
    "Base de mídia/Locuções.wav": 452,
    "Fotos/Ensaio primavera.tar": 980,
    "Documentos/Portfólio.pdf": 181,
    "Referências.zip": 98,
}


def main():
    app = QApplication(["DiskMap Studio"])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    with tempfile.TemporaryDirectory(prefix="diskmap-demo-") as sandbox:
        root = Path(sandbox) / "Estúdio Criativo"
        for relative, size in FIXTURE.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as handle:
                handle.truncate(size * MIB)
        database = Path(sandbox) / "demo.sqlite3"
        initialize(database)
        window = Window(database)
        window.show()
        window.start_scan(root)
        deadline = QTimer(window, singleShot=True, interval=15000)
        deadline.timeout.connect(lambda: app.exit(2))
        deadline.start()

        def save():
            if window.job or not window.file_table.rowCount():
                QTimer.singleShot(50, save)
                return
            window.location.setText("Estúdio Criativo · pasta de demonstração")
            if not window.grab().save(str(Path(sys.argv[1]))):
                app.exit(1)
                return
            window.close()

        QTimer.singleShot(100, save)
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
