"""Qt graphics view backed by the Squarify layout library."""
import html

import squarify
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

PALETTE = ("#f1a45f", "#dc834b", "#bc6740", "#9b543c", "#71524b", "#534b47", "#403d3b")


def readable_size(value):
    number = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"):
        if number < 1024 or unit == "EiB":
            return f"{value} B" if unit == "B" else f"{number:.1f} {unit}".replace(".", ",")
        number /= 1024


class Treemap(QGraphicsView):
    opened = Signal(int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.items_data = []
        self.setAccessibleName("Treemap de tamanhos. Use a árvore para navegação por teclado.")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(154)
        self.scene().setBackgroundBrush(QColor("#201e1c"))

    def show_nodes(self, rows, remainder):
        self.items_data = [(row["name"], row["bytes"], row["id"] if row["directory"] else 0)
                           for row in rows if row["bytes"] > 0]
        if remainder > 0:
            self.items_data.append(("Outros itens", remainder, 0))
        self.items_data.sort(key=lambda item: item[1], reverse=True)
        self.redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redraw()

    def redraw(self):
        scene = self.scene()
        scene.clear()
        width, height = self.viewport().width(), self.viewport().height()
        scene.setSceneRect(0, 0, width, height)
        if not self.items_data or width < 3 or height < 3:
            text = scene.addSimpleText("Nenhum tamanho para exibir nesta pasta.")
            text.setBrush(QColor("#c4bcb3"))
            text.setPos(16, 16)
            return
        sizes = squarify.normalize_sizes([item[1] for item in self.items_data], width, height)
        rectangles = squarify.squarify(sizes, 0, 0, width, height)
        for index, (rect, (name, size, node_id)) in enumerate(zip(rectangles, self.items_data)):
            x, y, w, h = (rect[key] for key in ("x", "y", "dx", "dy"))
            if w < 2 or h < 2:
                continue
            color_index = min(index, len(PALETTE) - 1)
            tile = scene.addRect(x + 1, y + 1, w - 2, h - 2, QPen(Qt.PenStyle.NoPen),
                                 QBrush(QColor(PALETTE[color_index])))
            tile.setData(0, node_id)
            tile.setToolTip(f"{html.escape(name)}<br>{readable_size(size)}" + ("<br>Duplo clique para abrir" if node_id else ""))
            if node_id:
                tile.setCursor(Qt.CursorShape.PointingHandCursor)
            if w > 60 and h > 30:
                label = scene.addSimpleText("", QFont("Sans Serif", 10, QFont.Weight.DemiBold))
                metrics = QFontMetrics(label.font())
                label.setText(metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(w) - 16))
                label.setBrush(QColor("#201710" if color_index < 3 else "#fff3e8"))
                label.setPos(x + 8, y + 7)
                label.setData(0, node_id)
                label.setToolTip(tile.toolTip())
                if h > 54:
                    count = scene.addSimpleText(readable_size(size))
                    count.setBrush(label.brush())
                    count.setPos(x + 8, y + 29)
                    count.setData(0, node_id)
                    count.setToolTip(tile.toolTip())

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0):
            self.opened.emit(item.data(0))
        super().mouseDoubleClickEvent(event)
