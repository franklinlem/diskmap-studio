import csv
import errno
import json
import os
from contextlib import closing, contextmanager

import pytest

from diskmap.export import export
from diskmap.scan import scan
from diskmap.store import (
    FileFilter, connect, differences, directory, discard_unsaved, files, history, initialize, keep_snapshot,
)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "origem"
    root.mkdir()
    db = tmp_path / "index.sqlite3"
    initialize(db)
    return root, db


def collect(db, root, cancelled=lambda: False, progress=lambda *_: None, **options):
    return scan(db, root, cancelled, progress, **options)


def test_size_tree_filters_and_paging(workspace):
    root, db = workspace
    folder = root / "Vídeos"
    folder.mkdir()
    (folder / "FÉRIAS.MP4").write_bytes(b"video")
    (root / "a.txt").write_bytes(b"two")
    (root / "b.txt").write_bytes(b"two")
    (root / "empty").touch()
    result = collect(db, root)
    assert (result["state"], result["files"], result["bytes"]) == ("complete", 4, 11)
    with closing(connect(db)) as connection:
        scan_id = result["id"]
        top = directory(connection, scan_id, 0)[0]
        assert top["bytes"] == 11
        assert directory(connection, scan_id, top["id"])[0]["bytes"] == 5
        matches = files(connection, scan_id, FileFilter("férias", ".MP4")).fetchall()
        assert [row["name"] for row in matches] == ["FÉRIAS.MP4"]
        first = files(connection, scan_id, FileFilter(extension="txt"), limit=1).fetchone()
        second = files(connection, scan_id, FileFilter(extension="txt"), after=(first["bytes"], first["id"])).fetchall()
        assert len(second) == 1 and second[0]["id"] != first["id"]


@pytest.mark.skipif(os.name != "posix", reason="Fixture uses symlink and FIFO APIs")
def test_links_and_special_files_are_skipped(workspace):
    root, db = workspace
    (root / "cycle").symlink_to(root, target_is_directory=True)
    (root / "broken").symlink_to(root / "absent")
    (root / "directory").mkdir()
    outside = root.parent / "outside.txt"
    outside.write_text("should not be counted")
    (root / "shortcut").symlink_to(outside)
    os.mkfifo(root / "queue")
    result = collect(db, root)
    assert result["files"] == 0
    assert json.loads(result["details"]) == {"Link ou redirecionamento": 3, "Arquivo especial": 1}
    with pytest.raises(ValueError):
        collect(db, root / "cycle")
    with pytest.raises(OSError):
        collect(db, root / "cycle" / "directory")


def test_mount_permission_and_vanished_directory(workspace, monkeypatch):
    import diskmap.scan as core
    root, db = workspace
    for name in ("mount", "denied", "gone", "normal"):
        directory_path = root / name
        directory_path.mkdir()
        (directory_path / "file").write_bytes(b"x")
    monkeypatch.setattr(core, "mounts", lambda: {root / "mount"})
    effective_open = core.open_directory

    @contextmanager
    def open_fixture(path, expected, parent_fd):
        if path.name == "denied":
            raise PermissionError(errno.EACCES, "denied")
        if path.name == "gone":
            raise FileNotFoundError(errno.ENOENT, "gone")
        with effective_open(path, expected, parent_fd) as opened:
            yield opened

    monkeypatch.setattr(core, "open_directory", open_fixture)
    result = collect(db, root)
    assert result["files"] == 1
    assert json.loads(result["details"]) == {
        "Ponto de montagem": 1, "Permissão negada": 1, "Caminho alterado ou indisponível": 1,
    }


def test_partial_runs_progress_and_snapshot_guard(workspace):
    root, db = workspace
    for index in range(550):
        (root / str(index)).touch()
    stopped = False
    updates = []

    def progress(scanned, *_):
        nonlocal stopped
        updates.append(scanned)
        stopped = True

    result = collect(db, root, lambda: stopped, progress)
    assert 0 < updates[0] <= 512
    assert result["state"] == "cancelled" and result["files"] < 550
    assert not keep_snapshot(db, result["id"])
    limited = collect(db, root, max_entries=4)
    assert limited["state"] == "limited" and limited["files"] == 4
    assert not keep_snapshot(db, limited["id"])


def test_snapshots_persist_and_compare(workspace):
    root, db = workspace
    (root / "grow").write_bytes(b"x")
    (root / "remove").write_bytes(b"x")
    (root / "switch").write_bytes(b"xx")
    first = collect(db, root)
    assert keep_snapshot(db, first["id"])
    (root / "grow").write_bytes(b"xxx")
    (root / "remove").unlink()
    (root / "new").write_bytes(b"xx")
    (root / "switch").unlink()
    (root / "switch").mkdir()
    second = collect(db, root)
    assert keep_snapshot(db, second["id"])
    discard_unsaved(db)
    initialize(db)
    assert len(history(db)) == 2
    with closing(connect(db)) as connection:
        changes = differences(connection, first["id"], second["id"])
        assert [(row["path"], row["change"], row["before"], row["after"]) for row in changes] == [
            (b"grow", "Alterado", 1, 3), (b"new", "Adicionado", None, 2),
            (b"remove", "Removido", 1, None), (b"switch", "Removido", 2, None),
        ]
        assert differences(connection, second["id"], first["id"])[-1]["change"] == "Adicionado"
        assert differences(connection, first["id"], second["id"], after=b"remove")[0]["path"] == b"switch"


def test_exports_escape_input_and_never_overwrite(workspace):
    root, db = workspace
    fancy = "-relatório&.TXT"
    (root / fancy).write_bytes(b"x")
    (root / "hidden.md").touch()
    if os.name == "posix":
        (root / "<script>.txt").touch()
    result = collect(db, root)
    csv_target = root.parent / "report.csv"
    html_target = root.parent / "report.html"
    export(db, result["id"], FileFilter(extension="txt"), csv_target, "CSV")
    with csv_target.open(encoding="utf-8-sig", newline="") as report:
        rows = list(csv.reader(report))
    assert rows[1] == ["'" + fancy, "txt", "1"]
    assert "hidden.md" not in str(rows)
    export(db, result["id"], FileFilter(extension="txt"), html_target, "HTML")
    page = html_target.read_text(encoding="utf-8")
    assert "&amp;" in page and "<script>" not in page
    if os.name == "posix":
        assert "&lt;script&gt;" in page
    with pytest.raises(FileExistsError):
        export(db, result["id"], FileFilter(), html_target, "HTML")
    assert html_target.read_text(encoding="utf-8") == page
