import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from diskmap.store import initialize

from diskmap.ui import Window


def wait_until(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(25)
    assert predicate()


def test_window_scan_tree_filter_history(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app
    root = tmp_path / "data"
    root.mkdir()
    (root / "bundle").mkdir()
    (root / "bundle" / "video.mkv").write_bytes(b"film")
    (root / "note.txt").write_bytes(b"note")
    database = tmp_path / "data.sqlite3"
    initialize(database)
    window = Window(database)
    window.show()
    try:
        window.start_scan(root)
        wait_until(lambda: window.job is None and window.file_table.rowCount() == 2)
        assert window.tree.topLevelItem(0).childCount() == 2
        assert len(window.map.items_data) == 2
        QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        assert window.search.hasFocus()
        window.extension.setText("mkv")
        wait_until(lambda: window.file_table.rowCount() == 1 and window.job is None)
        assert window.file_table.item(0, 0).text().endswith("video.mkv")
        assert not window.save_snapshot.isEnabled()
        window.license_holder = "Pessoa de teste"
        window.update_edition()
        window.save_current()
        assert window.snapshots.rowCount() == 1
    finally:
        window.close()
        wait_until(lambda: not window.isVisible())
