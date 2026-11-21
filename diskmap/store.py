"""Exclusively local storage for scan metadata and saved snapshots."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, root BLOB NOT NULL,
    created TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    saved INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'running',
    files INTEGER NOT NULL DEFAULT 0, bytes INTEGER NOT NULL DEFAULT 0,
    omitted INTEGER NOT NULL DEFAULT 0, details TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS nodes (
    scan INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    id INTEGER NOT NULL, parent INTEGER NOT NULL, path BLOB NOT NULL,
    name TEXT NOT NULL, ext TEXT NOT NULL, directory INTEGER NOT NULL,
    bytes INTEGER NOT NULL, mtime INTEGER NOT NULL,
    PRIMARY KEY (scan,id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS children ON nodes(scan,parent,bytes DESC,id);
CREATE INDEX IF NOT EXISTS largest ON nodes(scan,directory,bytes DESC,id);
CREATE INDEX IF NOT EXISTS extensions ON nodes(scan,directory,ext,bytes DESC,id);
CREATE UNIQUE INDEX IF NOT EXISTS paths ON nodes(scan,path);
"""


@dataclass(frozen=True)
class FileFilter:
    text: str = ""
    extension: str = ""

    def sql(self, scan_id):
        clauses = ["scan = ?", "directory = 0"]
        params = [scan_id]
        if self.extension:
            clauses.append("ext = ?")
            params.append(self.extension.casefold().lstrip("."))
        if self.text:
            clauses.append("instr(casefold(display_path(path)), ?) > 0")
            params.append(self.text.casefold())
        return " AND ".join(clauses), params


def display_path(raw):
    return raw.decode("utf-8", errors="backslashreplace")


def path_key(path):
    return str(path).encode("utf-8", errors="surrogatepass")


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.create_function("casefold", 1, str.casefold, deterministic=True)
    db.create_function("display_path", 1, display_path, deterministic=True)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA cache_size = -8192")
    db.execute("PRAGMA temp_store = FILE")
    return db


def initialize(path):
    with closing(connect(path)) as db, db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)
        db.execute("DELETE FROM scans WHERE saved = 0")


def keep_snapshot(path, scan_id):
    with closing(connect(path)) as db, db:
        row = db.execute(
            "UPDATE scans SET saved = 1 WHERE id = ? AND state = 'complete'",
            (scan_id,),
        )
        return row.rowcount == 1


def discard_unsaved(path, *, except_id=0):
    with closing(connect(path)) as db, db:
        db.execute("DELETE FROM scans WHERE saved = 0 AND id != ?", (except_id,))


def history(path, offset=0, limit=101):
    with closing(connect(path)) as db:
        return db.execute(
            "SELECT * FROM scans WHERE saved = 1 ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def directory(db, scan_id, parent_id, after=None, limit=101):
    query = "SELECT * FROM nodes WHERE scan = ? AND parent = ?"
    params = [scan_id, parent_id]
    if after:
        size, node_id = after
        query += " AND (bytes < ? OR (bytes = ? AND id > ?))"
        params.extend((size, size, node_id))
    return db.execute(query + " ORDER BY bytes DESC, id LIMIT ?", (*params, limit)).fetchall()


def files(db, scan_id, file_filter, after=None, limit=None):
    where, params = file_filter.sql(scan_id)
    if after:
        size, node_id = after
        where += " AND (bytes < ? OR (bytes = ? AND id > ?))"
        params.extend((size, size, node_id))
    query = f"SELECT * FROM nodes WHERE {where} ORDER BY bytes DESC, id"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return db.execute(query, params)


def differences(db, previous, current, after=b"", limit=101):
    rows = db.execute("SELECT id, root, saved FROM scans WHERE id IN (?, ?)", (previous, current)).fetchall()
    if len(rows) != 2 or rows[0]["root"] != rows[1]["root"] or not all(row["saved"] for row in rows):
        raise ValueError("Selecione dois snapshots da mesma origem.")
    return db.execute("""
        SELECT a.path AS path, a.bytes AS before, b.bytes AS after,
               CASE WHEN b.id IS NULL THEN 'Removido' ELSE 'Alterado' END AS change
        FROM nodes a LEFT JOIN nodes b
            ON b.scan = :current AND b.path = a.path AND b.directory = 0
        WHERE a.scan = :previous AND a.directory = 0 AND a.path > :after
          AND (b.id IS NULL OR a.bytes != b.bytes OR a.mtime != b.mtime)
        UNION ALL
        SELECT b.path, NULL, b.bytes, 'Adicionado'
        FROM nodes b LEFT JOIN nodes a
            ON a.scan = :previous AND a.path = b.path AND a.directory = 0
        WHERE b.scan = :current AND b.directory = 0 AND b.path > :after AND a.id IS NULL
        ORDER BY path LIMIT :limit
    """, {"previous": previous, "current": current, "after": after, "limit": limit}).fetchall()
