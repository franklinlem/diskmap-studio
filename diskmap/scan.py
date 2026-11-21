"""Incremental, metadata-only traversal of a selected tree."""
import errno
import json
import os
import re
import stat
import sys
from collections import Counter
from contextlib import closing, contextmanager
from pathlib import Path

from .store import connect, display_path, path_key

BATCH_SIZE = 512
MAX_DEPTH = 96
MAX_ENTRIES = 2_000_000
MAX_INT = (1 << 63) - 1
HAS_DIR_FDS = os.open in os.supports_dir_fd and os.scandir in os.supports_fd
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def mounts():
    if not sys.platform.startswith("linux"):
        return set()
    result = set()
    try:
        with open("/proc/self/mountinfo", "rb") as table:
            for line in table:
                point = re.sub(rb"\\([0-7]{3})", lambda match: bytes([int(match[1], 8)]), line.split()[4])
                result.add(Path(os.fsdecode(point)))
    except OSError:
        pass
    return result


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & REPARSE_POINT
    )


def identity(info):
    return info.st_dev, info.st_ino


def reason(error):
    if isinstance(error, PermissionError):
        return "Permissão negada"
    if isinstance(error, (FileNotFoundError, NotADirectoryError)) or error.errno in (errno.ELOOP, errno.ESTALE):
        return "Caminho alterado ou indisponível"
    return "Erro de leitura"


@contextmanager
def open_directory(path, expected, parent_fd=None):
    if HAS_DIR_FDS:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        if parent_fd is None:
            fd = os.open(path.anchor, flags)
            try:
                for component in path.parts[1:]:
                    child_fd = os.open(component, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child_fd
                if identity(os.fstat(fd)) != identity(expected):
                    raise FileNotFoundError(path)
                with os.scandir(fd) as entries:
                    yield entries, fd
            finally:
                os.close(fd)
        else:
            fd = os.open(path.name, flags, dir_fd=parent_fd)
            try:
                if identity(os.fstat(fd)) != identity(expected):
                    raise FileNotFoundError(path)
                with os.scandir(fd) as entries:
                    yield entries, fd
            finally:
                os.close(fd)
    else:
        # Windows scandir takes a path. Check every ancestor for junctions.
        for parent in reversed(path.parents):
            if linked(parent.lstat()):
                raise FileNotFoundError(parent)
        current = path.lstat()
        if linked(current) or identity(current) != identity(expected):
            raise FileNotFoundError(path)
        with os.scandir(path) as entries:
            current = path.lstat()
            if linked(current) or identity(current) != identity(expected):
                raise FileNotFoundError(path)
            yield entries, None


def scan(database, root, cancelled, report, *, max_entries=MAX_ENTRIES):
    root = Path(os.path.abspath(root))
    root_info = root.lstat()
    if linked(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ValueError("A origem deve ser uma pasta ou unidade sem redirecionamento.")
    mount_paths = mounts()
    index = Path(os.path.abspath(database))
    internal_files = {index.with_name(index.name + suffix) for suffix in ("", "-wal", "-shm", "-journal")}
    internal_files.update((index.with_suffix(".lock"), index.with_name("pro.diskmap-license")))
    omitted = Counter()
    pending = []
    totals = []
    scanned = file_count = byte_count = next_id = 0
    limited = False

    with closing(connect(database)) as db:
        cursor = db.execute("INSERT INTO scans(root) VALUES (?)", (path_key(root),))
        scan_id = cursor.lastrowid
        db.commit()

        def flush(path):
            db.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", pending)
            db.executemany("UPDATE nodes SET bytes = ? WHERE scan = ? AND id = ?", totals)
            db.commit()
            pending.clear()
            totals.clear()
            report(scanned, file_count, byte_count, display_path(path_key(path)))

        def add(path, relative, parent, info, is_directory):
            nonlocal next_id
            next_id += 1
            name = display_path(path_key(path.name or str(path)))
            extension = Path(name).suffix.lstrip(".").casefold() if not is_directory else ""
            pending.append((
                scan_id, next_id, parent, path_key(relative), name, extension, int(is_directory),
                0 if is_directory else info.st_size, info.st_mtime_ns,
            ))
            if len(pending) + len(totals) >= BATCH_SIZE:
                flush(path)
            return next_id

        def walk(path, relative, node_id, info, ancestors, depth, parent_fd=None):
            nonlocal scanned, file_count, byte_count, limited
            total = 0
            try:
                with open_directory(path, info, parent_fd) as (entries, fd):
                    for entry in entries:
                        if cancelled() or limited:
                            break
                        if scanned >= max_entries:
                            limited = True
                            omitted["Limite de itens atingido"] += 1
                            break
                        scanned += 1
                        child = path / entry.name
                        child_relative = relative / entry.name
                        if child in internal_files:
                            continue
                        if scanned % BATCH_SIZE == 0:
                            flush(child)
                        try:
                            item = entry.stat(follow_symlinks=False) if fd is not None else child.lstat()
                        except OSError as error:
                            omitted[reason(error)] += 1
                            continue
                        if linked(item):
                            omitted["Link ou redirecionamento"] += 1
                        elif item.st_dev != root_info.st_dev or child in mount_paths:
                            omitted["Ponto de montagem"] += 1
                        elif stat.S_ISDIR(item.st_mode):
                            key = identity(item)
                            if key[1] and key in ancestors:
                                omitted["Ciclo de diretórios"] += 1
                            elif depth >= MAX_DEPTH:
                                omitted["Limite de profundidade"] += 1
                            else:
                                child_id = add(child, child_relative, node_id, item, True)
                                total += walk(child, child_relative, child_id, item, ancestors | {key}, depth + 1, fd)
                        elif stat.S_ISREG(item.st_mode):
                            if item.st_size < 0 or item.st_size > MAX_INT - byte_count:
                                omitted["Limite de tamanho"] += 1
                                limited = True
                                break
                            file_count += 1
                            byte_count += item.st_size
                            total += item.st_size
                            add(child, child_relative, node_id, item, False)
                        else:
                            omitted["Arquivo especial"] += 1
                    final = os.fstat(fd) if fd is not None else path.lstat()
                    if identity(final) != identity(info) or linked(final) or final.st_mtime_ns != info.st_mtime_ns:
                        omitted["Pasta modificada durante a leitura"] += 1
            except OSError as error:
                if depth == 0:
                    raise
                omitted[reason(error)] += 1
            totals.append((total, scan_id, node_id))
            if len(pending) + len(totals) >= BATCH_SIZE:
                flush(path)
            return total

        try:
            root_id = add(root, Path("."), 0, root_info, True)
            walk(root, Path("."), root_id, root_info, {identity(root_info)}, 0)
            flush(root)
            state = "cancelled" if cancelled() else "limited" if limited else "complete"
            details = json.dumps(dict(omitted), ensure_ascii=False)
            with db:
                db.execute(
                    "UPDATE scans SET state=?, files=?, bytes=?, omitted=?, details=? WHERE id=?",
                    (state, file_count, byte_count, sum(omitted.values()), details, scan_id),
                )
            return db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        except Exception:
            with db:
                db.execute("DELETE FROM scans WHERE id=?", (scan_id,))
            raise
