"""Stream metadata into user-selected, newly created report files."""
import csv
import html
from contextlib import closing
from pathlib import Path

from .store import connect, display_path, files


def safe_cell(text):
    # Spreadsheet software can execute formula-leading cells.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export(database, scan_id, file_filter, target, kind):
    target = Path(target)
    # Exclusive creation also refuses symlinks and existing hard links.
    with closing(connect(database)) as db:
        scan = db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        rows = files(db, scan_id, file_filter)
        with target.open("x", encoding="utf-8-sig" if kind == "CSV" else "utf-8", newline="") as output:
            if kind == "CSV":
                writer = csv.writer(output)
                writer.writerow(("Caminho relativo", "Extensão", "Bytes"))
                for row in rows:
                    writer.writerow((safe_cell(display_path(row["path"])), safe_cell(row["ext"]), row["bytes"]))
                return
            output.write("""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório | DiskMap Studio</title><style>
body{font:1rem system-ui;max-width:75rem;margin:2rem auto;padding:0 1rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #aaa;padding:.5rem;text-align:left;overflow-wrap:anywhere}
</style><main><h1>Relatório DiskMap Studio</h1>""")
            states = {"complete": "Concluída", "limited": "Limite atingido", "cancelled": "Cancelada"}
            output.write(f'<p>Origem: <code>{html.escape(display_path(scan["root"]))}</code></p>')
            output.write(f'<p>Estado: {states[scan["state"]]} · Ocorrências: {scan["omitted"]}</p>')
            output.write("<table><thead><tr><th>Caminho relativo</th><th>Extensão</th><th>Bytes</th></tr></thead><tbody>")
            for row in rows:
                name = html.escape(display_path(row["path"]))
                extension = html.escape(row["ext"])
                output.write(f"<tr><td>{name}</td><td>{extension}</td><td>{row['bytes']}</td></tr>\n")
            output.write("</tbody></table></main></html>")
