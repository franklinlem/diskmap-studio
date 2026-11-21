"""DiskMap Studio desktop interface and worker coordination."""
import html
import json
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import Event

from PySide6.QtCore import QIODevice, QSaveFile, QStorageInfo, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHeaderView,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .export import export
from .license import read_license, verify
from .scan import scan
from .store import (
    FileFilter, connect, differences, directory, discard_unsaved, display_path, files,
    history, keep_snapshot,
)
from .treemap import Treemap, readable_size

ROLE = Qt.ItemDataRole.UserRole
PAGE = 100
STATES = {"complete": "Concluída", "cancelled": "Cancelada", "limited": "Limite atingido"}


class Job(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, object, str)

    def __init__(self, work, parent):
        super().__init__(parent)
        self.work = work
        self.stop = Event()
        self.last_update = 0.0

    def report(self, scanned, count, size, path):
        now = time.monotonic()
        if now - self.last_update >= 0.12:
            self.last_update = now
            self.progress.emit(scanned, count, size, path)

    def run(self):
        try:
            self.succeeded.emit(self.work(self))
        except Exception as error:
            self.failed.emit(str(error).encode("utf-8", "backslashreplace").decode("utf-8"))


def integer(value):
    return f"{value:,}".replace(",", ".")


def label(text="", kind=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if kind:
        widget.setObjectName(kind)
    return widget


def button(text, callback, *, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    return widget


def plain_tip(text):
    return "<p>" + html.escape(str(text)) + "</p>"


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for index, row in enumerate(rows):
        for column, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            item.setToolTip(plain_tip(value))
            widget.setItem(index, column, item)


class Window(QMainWindow):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.result = None
        self.license_path = database.with_name("pro.diskmap-license")
        try:
            self.license_holder = verify(read_license(self.license_path))
        except (OSError, ValueError):
            self.license_holder = ""
        self.job = None
        self.job_kind = ""
        self.closing = False
        self.refresh_pending = False
        self.file_cursor = None
        self.file_pages = []
        self.history_offset = 0
        self.compare_pair = None
        self.compare_cursor = b""
        self.setWindowTitle("DiskMap Studio")
        self.setMinimumSize(720, 640)
        self.resize(1140, 820)
        self.build()
        self.update_edition()
        self.refresh_controls()

    def build(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(10)
        header = QFrame(objectName="header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(13, 9, 11, 9)
        brand = label("DiskMap Studio", "wordmark")
        header_layout.addWidget(brand)
        header_layout.addStretch()
        self.unit_button = button("&Unidades", self.choose_unit)
        self.folder_button = button("&Selecionar pasta", self.choose_folder, primary=True)
        self.cancel_button = button("&Cancelar", self.cancel_scan)
        for control in (self.unit_button, self.folder_button, self.cancel_button):
            header_layout.addWidget(control)
        outer.addWidget(header)

        self.summary = label("Selecione uma unidade ou pasta", "summary")
        self.location = label("A varredura lê apenas os metadados dos arquivos.")
        self.location.setProperty("muted", True)
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.summary)
        outer.addWidget(self.location)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setAccessibleName("Área redimensionável de pastas e treemap")
        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 7, 0)
        tree_layout.addWidget(label("Pastas e arquivos", "section"))
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Árvore de pastas e arquivos")
        self.tree.setHeaderLabels(["Nome", "Tamanho"])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemExpanded.connect(self.expand_tree)
        self.tree.itemCollapsed.connect(self.collapse_tree)
        self.tree.currentItemChanged.connect(self.tree_selected)
        self.tree.itemActivated.connect(self.activate_tree_item)
        tree_layout.addWidget(self.tree)
        workspace.addWidget(tree_panel)

        map_panel = QWidget()
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(7, 0, 0, 0)
        self.map_caption = label("Treemap", "section")
        self.map_caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        map_layout.addWidget(self.map_caption)
        self.map = Treemap()
        self.map.opened.connect(self.open_from_map)
        map_layout.addWidget(self.map)
        workspace.addWidget(map_panel)
        workspace.setSizes([370, 730])
        workspace.setChildrenCollapsible(False)

        self.tabs = QTabWidget()
        self.build_files()
        self.build_history()
        split = QSplitter(Qt.Orientation.Vertical)
        split.setAccessibleName("Área redimensionável de visualização e resultados")
        split.addWidget(workspace)
        split.addWidget(self.tabs)
        split.setSizes([420, 285])
        split.setChildrenCollapsible(False)
        outer.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.status = label("Pronto")
        self.status.setAccessibleName("Estado da operação")
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Progresso da operação")
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(110)
        self.progress.hide()
        self.details = button("Ocorrências", self.show_details)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.progress)
        bottom.addWidget(self.details)
        outer.addLayout(bottom)
        self.setCentralWidget(central)
        self.shortcut("Ctrl+O", self.choose_folder)
        self.shortcut("Ctrl+F", self.focus_search)
        self.shortcut("Esc", self.cancel_scan)

    def shortcut(self, key, action):
        command = QAction(self)
        command.setShortcut(QKeySequence(key))
        command.triggered.connect(action)
        self.addAction(command)

    def build_files(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        controls = QWidget(objectName="filters")
        line = QHBoxLayout(controls)
        line.setContentsMargins(6, 4, 6, 4)
        self.search = QLineEdit(placeholderText="Nome ou caminho")
        self.search.setAccessibleName("Pesquisar arquivos")
        self.extension = QLineEdit(placeholderText="Ex. pdf")
        self.extension.setAccessibleName("Filtrar por extensão")
        self.extension.setMaximumWidth(120)
        search_label = label("&Buscar")
        search_label.setBuddy(self.search)
        ext_label = label("&Extensão")
        ext_label.setBuddy(self.extension)
        line.addWidget(search_label)
        line.addWidget(self.search, 1)
        line.addWidget(ext_label)
        line.addWidget(self.extension)
        self.csv_button = button("CSV", lambda: self.export_result("CSV"))
        self.html_button = button("HTML", lambda: self.export_result("HTML"))
        self.csv_button.setAccessibleName("Exportar arquivos filtrados em CSV")
        self.html_button.setAccessibleName("Exportar arquivos filtrados em HTML")
        line.addWidget(self.csv_button)
        line.addWidget(self.html_button)
        layout.addWidget(controls)
        self.file_table = table(["Caminho relativo", "Extensão", "Tamanho"])
        self.file_table.setAccessibleName("Maiores arquivos da origem selecionada")
        layout.addWidget(self.file_table, 1)
        paging = QHBoxLayout()
        self.files_info = label("Nenhuma varredura aberta")
        self.previous_files = button("Anterior", lambda: self.change_file_page(-1))
        self.next_files = button("Próxima", lambda: self.change_file_page(1))
        paging.addWidget(self.files_info, 1)
        paging.addWidget(self.previous_files)
        paging.addWidget(self.next_files)
        layout.addLayout(paging)
        self.tabs.addTab(panel, "Maiores arquivos")
        self.search_timer = QTimer(self, singleShot=True, interval=220)
        self.search_timer.timeout.connect(self.reset_files)
        self.search.textChanged.connect(self.schedule_filter)
        self.extension.textChanged.connect(self.schedule_filter)

    def build_history(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        controls = QHBoxLayout()
        self.pro_status = label("Histórico local")
        controls.addWidget(self.pro_status, 1)
        self.save_snapshot = button("Salvar snapshot", self.save_current)
        self.open_snapshot = button("Abrir", self.open_saved)
        self.compare_snapshots = button("Comparar seleção", self.start_comparison)
        for widget in (self.save_snapshot, self.open_snapshot, self.compare_snapshots):
            controls.addWidget(widget)
        layout.addLayout(controls)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.snapshots = table(["Origem", "Data local", "Arquivos", "Tamanho", "Ocorrências"])
        self.snapshots.setAccessibleName("Snapshots. Selecione dois da mesma origem com Control ou Shift.")
        self.snapshots.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.snapshots.itemSelectionChanged.connect(self.refresh_controls)
        self.snapshots.itemDoubleClicked.connect(lambda _: self.open_saved())
        splitter.addWidget(self.snapshots)
        self.diff_table = table(["Caminho relativo", "Mudança", "Antes", "Depois", "Variação"])
        self.diff_table.setAccessibleName("Diferenças entre snapshots")
        splitter.addWidget(self.diff_table)
        layout.addWidget(splitter, 1)
        paging = QHBoxLayout()
        self.previous_history = button("Snapshots anteriores", lambda: self.load_history(-1))
        self.next_history = button("Mais snapshots", lambda: self.load_history(1))
        self.diff_info = label("Selecione dois snapshots da mesma origem.")
        self.next_diff = button("Mais diferenças", self.load_diff)
        for widget in (self.previous_history, self.next_history):
            paging.addWidget(widget)
        paging.addWidget(self.diff_info, 1)
        paging.addWidget(self.next_diff)
        layout.addLayout(paging)
        self.editions = QStackedWidget()
        locked = QWidget()
        locked_layout = QVBoxLayout(locked)
        locked_layout.addStretch()
        locked_layout.addWidget(label("Histórico de snapshots", "section"))
        explanation = label("Com o Pro, salve varreduras e compare mudanças sem sair do computador.")
        explanation.setWordWrap(True)
        locked_layout.addWidget(explanation)
        activate = button("Importar licença Pro", self.activate_license, primary=True)
        locked_layout.addWidget(activate, alignment=Qt.AlignmentFlag.AlignLeft)
        locked_layout.addStretch()
        self.editions.addWidget(locked)
        self.editions.addWidget(panel)
        self.tabs.addTab(self.editions, "Histórico Pro")

    def update_edition(self):
        if self.license_holder:
            self.pro_status.setToolTip(plain_tip(f"Licença Pro de {self.license_holder}"))
            self.editions.setCurrentIndex(1)
            self.load_history()

    def activate_license(self):
        source, _ = QFileDialog.getOpenFileName(
            self, "Importar licença Pro", "", "Licença DiskMap (*.diskmap-license);;Todos os arquivos (*)"
        )
        if not source:
            return
        try:
            blob = read_license(Path(source))
            holder = verify(blob)
            target = QSaveFile(str(self.license_path))
            if not target.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(target.errorString())
            if target.write(blob) != len(blob) or not target.commit():
                raise OSError(target.errorString())
        except (OSError, ValueError) as error:
            self.show_error(str(error))
            return
        self.license_holder = holder
        self.update_edition()
        self.status.setText("Licença Pro ativada neste computador.")

    def focus_search(self):
        self.tabs.setCurrentIndex(0)
        self.search.setFocus()

    def choose_folder(self):
        if self.job:
            return
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta para analisar")
        if folder:
            self.start_scan(folder)

    def choose_unit(self):
        if self.job:
            return
        volumes = [item for item in QStorageInfo.mountedVolumes() if item.isValid() and item.isReady()]
        if not volumes:
            self.status.setText("Nenhuma unidade disponível.")
            return
        choices = {f"{item.displayName() or 'Unidade'} ({item.rootPath()})": item.rootPath() for item in volumes}
        choice, ok = QInputDialog.getItem(self, "Selecionar unidade", "Unidade", sorted(choices), 0, False)
        if ok:
            self.start_scan(choices[choice])

    def launch(self, kind, work, accept):
        self.job_kind = kind
        self.job = Job(work, self)
        self.job.succeeded.connect(accept)
        self.job.failed.connect(self.show_error)
        self.job.finished.connect(self.finished)
        self.job.progress.connect(self.scan_progress)
        if kind != "consulta":
            self.progress.setRange(0, 0)
            self.progress.show()
        self.refresh_controls()
        self.job.start()

    def finished(self):
        self.job.deleteLater()
        self.job = None
        self.job_kind = ""
        self.progress.hide()
        if self.closing:
            self.close()
            return
        self.refresh_controls()
        if self.refresh_pending:
            self.refresh_pending = False
            self.reset_files()

    def show_error(self, text):
        self.status.setText("A operação falhou.")
        if not self.closing:
            dialog = QMessageBox(QMessageBox.Icon.Warning, "DiskMap Studio", text, parent=self)
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.exec()

    def start_scan(self, path):
        self.status.setText("Iniciando varredura…")

        def work(job):
            result = scan(self.database, path, job.stop.is_set, job.report)
            discard_unsaved(self.database, except_id=result["id"])
            return result

        self.launch("varredura", work, self.display_result)

    def cancel_scan(self):
        if self.job_kind == "varredura":
            self.job.stop.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelando após a leitura atual…")

    def scan_progress(self, scanned, count, size, path):
        if self.job and not self.job.stop.is_set():
            self.status.setText(f"{integer(scanned)} itens lidos · {integer(count)} arquivos · {readable_size(size)}")
            self.status.setToolTip(plain_tip(path))

    def display_result(self, result):
        self.result = result
        self.summary.setText(f"{readable_size(result['bytes'])}  /  {integer(result['files'])} arquivos")
        self.location.setText(display_path(result["root"]))
        self.status.setText(f"{STATES[result['state']]} · {result['omitted']} ocorrências")
        self.status.setToolTip("Abra Ocorrências para ver os motivos.")
        self.tree.clear()
        with closing(connect(self.database)) as db:
            row = directory(db, result["id"], 0, limit=1)[0]
        item = self.node_item(row)
        self.tree.addTopLevelItem(item)
        self.tree.setCurrentItem(item)
        item.setExpanded(True)
        self.reset_files()

    def node_item(self, row):
        item = QTreeWidgetItem([row["name"], readable_size(row["bytes"])])
        item.setData(0, ROLE, (row["id"], row["directory"], row["bytes"], row["name"]))
        item.setToolTip(0, plain_tip(display_path(row["path"])))
        item.setToolTip(1, f"{row['bytes']} bytes")
        if row["directory"]:
            item.addChild(QTreeWidgetItem(["Carregar…"]))
        return item

    def expand_tree(self, item):
        parent = item.parent()
        if parent is not None:
            for index in range(parent.childCount()):
                sibling = parent.child(index)
                if sibling is not item and sibling.isExpanded():
                    sibling.setExpanded(False)
        self.populate_tree(item, [None])

    def collapse_tree(self, item):
        if item.data(0, ROLE):
            item.takeChildren()
            item.addChild(QTreeWidgetItem(["Carregar…"]))
            item.setData(0, ROLE + 2, None)

    def populate_tree(self, item, pages):
        node = item.data(0, ROLE)
        if not node:
            return
        item.takeChildren()
        item.setData(0, ROLE + 2, pages)
        with closing(connect(self.database)) as db:
            rows = directory(db, self.result["id"], node[0], pages[-1], PAGE + 1)
        if len(pages) > 1:
            previous = QTreeWidgetItem(["Página anterior…"])
            previous.setData(0, ROLE + 1, -1)
            item.addChild(previous)
        item.addChildren([self.node_item(row) for row in rows[:PAGE]])
        if len(rows) > PAGE:
            more = QTreeWidgetItem(["Próxima página…"])
            more.setData(0, ROLE + 1, (rows[PAGE - 1]["bytes"], rows[PAGE - 1]["id"]))
            item.addChild(more)

    def activate_tree_item(self, item, _column):
        after = item.data(0, ROLE + 1)
        if after is None:
            return
        parent = item.parent()
        pages = parent.data(0, ROLE + 2)
        pages = pages[:-1] if after == -1 else [*pages, after]
        self.tree.setCurrentItem(parent)
        self.populate_tree(parent, pages)
        self.tree.setCurrentItem(parent.child(int(len(pages) > 1)))

    def tree_selected(self, item, _previous):
        if item is None or not item.data(0, ROLE):
            return
        node, is_dir, size, name = item.data(0, ROLE)
        self.map_caption.setText(f"Treemap / {name}")
        with closing(connect(self.database)) as db:
            if is_dir:
                rows = directory(db, self.result["id"], node, limit=44)
                remainder = size - sum(row["bytes"] for row in rows)
            else:
                rows = [db.execute("SELECT * FROM nodes WHERE scan=? AND id=?", (self.result["id"], node)).fetchone()]
                remainder = 0
        self.map.show_nodes(rows, remainder)

    def open_from_map(self, node_id):
        current = self.tree.currentItem()
        if current is None or not current.data(0, ROLE):
            return
        current.setExpanded(True)
        if len(current.data(0, ROLE + 2) or []) > 1:
            self.populate_tree(current, [None])
        for index in range(min(current.childCount(), PAGE)):
            child = current.child(index)
            if child.data(0, ROLE) and child.data(0, ROLE)[0] == node_id:
                self.tree.setCurrentItem(child)
                self.tree.scrollToItem(child)
                break

    def active_filter(self):
        return FileFilter(self.search.text().strip(), self.extension.text().strip())

    def schedule_filter(self):
        self.file_cursor = None
        self.previous_files.setEnabled(False)
        self.next_files.setEnabled(False)
        self.search_timer.start()

    def reset_files(self):
        if self.job:
            self.refresh_pending = True
            return
        self.file_pages = [None]
        self.load_files()

    def change_file_page(self, direction):
        if direction < 0:
            self.file_pages.pop()
        else:
            self.file_pages.append(self.file_cursor)
        self.load_files()

    def load_files(self):
        if not self.result:
            return
        scan_id = self.result["id"]
        file_filter = self.active_filter()
        after = self.file_pages[-1]
        self.files_info.setText("Consultando arquivos…")

        def work(_job):
            with closing(connect(self.database)) as db:
                return files(db, scan_id, file_filter, after, PAGE + 1).fetchall()

        def accept(rows):
            visible = rows[:PAGE]
            self.file_cursor = (visible[-1]["bytes"], visible[-1]["id"]) if len(rows) > PAGE else None
            fill_table(self.file_table, [(display_path(row["path"]), row["ext"] or "—",
                                         readable_size(row["bytes"])) for row in visible])
            self.files_info.setText(f"Página {len(self.file_pages)} · {len(visible)} arquivos" if visible else "Nenhum arquivo encontrado")

        self.launch("consulta", work, accept)

    def export_result(self, kind):
        dialog = QFileDialog(self, f"Exportar {kind}")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite)
        dialog.setNameFilter(f"{kind} (*.{kind.lower()})")
        dialog.setDefaultSuffix(kind.lower())
        dialog.selectFile(f"diskmap-relatorio.{kind.lower()}")
        if not dialog.exec():
            return
        target = Path(dialog.selectedFiles()[0])
        if target.exists() or target.is_symlink():
            self.show_error("O relatório precisa de um nome de arquivo novo.")
            return
        scan_id, file_filter = self.result["id"], self.active_filter()
        self.status.setText(f"Exportando {kind}…")
        self.launch("exportação", lambda _: export(self.database, scan_id, file_filter, target, kind),
                    lambda _: self.status.setText(f"Relatório {kind} exportado."))

    def show_details(self):
        if not self.result:
            return
        details = json.loads(self.result["details"])
        text = "\n".join(f"{key} — {value}" for key, value in sorted(details.items()))
        QMessageBox.information(self, "Ocorrências da varredura", text or "Nenhuma ocorrência registrada.")

    def load_history(self, direction=0):
        self.history_offset = max(0, self.history_offset + direction * PAGE)
        rows = history(self.database, self.history_offset)
        self.history_rows = rows[:PAGE]
        self.history_more = len(rows) > PAGE
        fill_table(self.snapshots, [
            (display_path(row["root"]), datetime.fromisoformat(row["created"]).astimezone().strftime("%d/%m/%Y %H:%M:%S"),
             row["files"], readable_size(row["bytes"]), row["omitted"]) for row in self.history_rows
        ])
        self.refresh_controls()

    def save_current(self):
        if self.license_holder and keep_snapshot(self.database, self.result["id"]):
            with closing(connect(self.database)) as db:
                self.result = db.execute("SELECT * FROM scans WHERE id=?", (self.result["id"],)).fetchone()
            self.history_offset = 0
            self.load_history()
            self.status.setText("Snapshot salvo no histórico local.")

    def selected_snapshots(self):
        if not hasattr(self, "history_rows"):
            return []
        return [self.history_rows[index.row()] for index in self.snapshots.selectionModel().selectedRows()
                if index.row() < len(self.history_rows)]

    def open_saved(self):
        if self.job:
            return
        selection = self.selected_snapshots()
        if len(selection) == 1:
            self.display_result(selection[0])
            self.tabs.setCurrentIndex(0)

    def start_comparison(self):
        selection = sorted(self.selected_snapshots(), key=lambda row: row["id"])
        self.compare_pair = tuple(row["id"] for row in selection)
        self.compare_cursor = b""
        self.compare_has_more = False
        self.compare_summary = (
            f"{readable_size(selection[0]['bytes'])} → {readable_size(selection[1]['bytes'])}"
            + (" · com ocorrências" if any(row["omitted"] for row in selection) else "")
        )
        self.load_diff()

    def load_diff(self):
        self.diff_info.setText("Comparando snapshots…")
        pair, after = self.compare_pair, self.compare_cursor

        def work(_job):
            with closing(connect(self.database)) as db:
                return differences(db, *pair, after=after, limit=PAGE + 1)

        def accept(rows):
            self.compare_has_more = len(rows) > PAGE
            visible = rows[:PAGE]
            if visible:
                self.compare_cursor = visible[-1]["path"]
            result = []
            for row in visible:
                before, after = row["before"], row["after"]
                delta = (after or 0) - (before or 0)
                change = ("+" if delta > 0 else "−" if delta < 0 else "") + readable_size(abs(delta))
                result.append((display_path(row["path"]), row["change"],
                               "—" if before is None else readable_size(before),
                               "—" if after is None else readable_size(after), change))
            fill_table(self.diff_table, result)
            self.diff_info.setText(self.compare_summary if visible else f"{self.compare_summary} · sem diferenças")

        self.launch("comparação", work, accept)

    def refresh_controls(self):
        idle = self.job is None
        self.folder_button.setEnabled(idle)
        self.unit_button.setEnabled(idle)
        self.cancel_button.setEnabled(self.job_kind == "varredura" and not self.job.stop.is_set())
        self.details.setEnabled(bool(self.result))
        self.csv_button.setEnabled(idle and bool(self.result))
        self.html_button.setEnabled(idle and bool(self.result))
        self.previous_files.setEnabled(idle and not self.search_timer.isActive() and len(self.file_pages) > 1)
        self.next_files.setEnabled(idle and not self.search_timer.isActive() and self.file_cursor is not None)
        self.save_snapshot.setEnabled(idle and bool(self.license_holder) and bool(self.result) and self.result["state"] == "complete" and not self.result["saved"])
        selected = self.selected_snapshots()
        self.open_snapshot.setEnabled(idle and len(selected) == 1)
        self.compare_snapshots.setEnabled(idle and len(selected) == 2 and selected[0]["root"] == selected[1]["root"])
        self.previous_history.setEnabled(idle and self.history_offset > 0)
        self.next_history.setEnabled(idle and getattr(self, "history_more", False))
        self.next_diff.setEnabled(idle and getattr(self, "compare_has_more", False))

    def closeEvent(self, event):
        if self.job:
            self.closing = True
            self.cancel_scan()
            event.ignore()
        else:
            event.accept()
