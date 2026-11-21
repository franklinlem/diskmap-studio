"""Palette for the Qt Widgets interface."""

STYLE = """
QWidget { background: #191817; color: #f5eee6; font-size: 13px; }
QFrame#header, QWidget#filters { background: #22201e; }
QFrame#header QLabel, QWidget#filters QLabel { background: transparent; }
QLabel#wordmark { font-size: 21px; font-weight: 700; color: #fff5eb; }
QLabel#section { font-size: 15px; font-weight: 650; }
QLabel[muted="true"] { color: #c6b9ad; }
QLabel#summary { font-size: 17px; color: #ffd0a3; font-weight: 650; }
QPushButton { background: #2d2926; border: 1px solid #595047; border-radius: 5px; padding: 6px 10px; }
QPushButton:hover { background: #40352c; }
QPushButton#primary { background: #ffad69; border-color: #ffad69; color: #251709; font-weight: 700; }
QPushButton#primary:hover { background: #ffc195; }
QPushButton:disabled { color: #9e9187; background: #252321; border-color: #403a35; }
QLineEdit, QComboBox { background: #191817; border: 1px solid #66574a; border-radius: 5px; padding: 7px; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QAbstractItemView:focus, QTabBar::tab:focus { border: 1px solid #ffbb83; }
QTreeWidget, QTableWidget { background: #211f1d; alternate-background-color: #272421; border: 1px solid #3a342f; gridline-color: #3a342f; }
QHeaderView::section { background: #2d2925; color: #eadbce; padding: 7px; border: 0; border-bottom: 1px solid #574538; }
QTreeView::item, QTableView::item { padding: 4px; }
QTreeView::item:selected, QTableView::item:selected { background: #77452b; color: #fff6ed; }
QTabWidget::pane { border: 1px solid #40372f; }
QTabBar::tab { background: #26221f; padding: 8px 15px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { border-bottom-color: #ffad69; color: #ffd2aa; }
QSplitter::handle { background: #3a322b; }
QProgressBar { border: 1px solid #675244; border-radius: 3px; background: #25211e; }
QProgressBar::chunk { background: #ffad69; }
QToolTip { background: #34291f; color: #fff6eb; border: 1px solid #876448; padding: 4px; }
"""
