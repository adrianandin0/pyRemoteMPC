"""
Theme Manager for pyRemoteMPC.
Provides 4 curated, non-bright themes: Dark, Light, Ocean, and Forest.
Supports real-time dynamic application across all Qt GUI widgets without hardcoded overrides.
"""

from PySide6.QtWidgets import QApplication


DARK_STYLESHEET = """
* { font-size: 11px; font-weight: normal; color: #cccccc; }
QWidget { background-color: #1e1e1e; color: #cccccc; }
QMainWindow, QDialog { background-color: #252526; }
QDockWidget { background-color: #1e1e1e; color: #cccccc; }
QDockWidget::title { background-color: #2d2d2d; color: #cccccc; padding: 4px; border-bottom: 1px solid #3c3c3c; }
QMainWindow::separator { background-color: #3c3c3c; width: 1px; height: 1px; image: none; }

QTabWidget::pane { border: 1px solid #3c3c3c; background-color: #1e1e1e; }
QTabBar::tab { background-color: #2d2d2d; color: #aaaaaa; padding: 6px 14px; border: 1px solid #3c3c3c; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background-color: #1e1e1e; color: #ffffff; font-weight: bold; border-bottom: 2px solid #007acc; }

QGroupBox { border: 1px solid #3c3c3c; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #007acc; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; color: #007acc; }

QLineEdit, QSpinBox, QComboBox { background-color: #252526; color: #ffffff; border: 1px solid #3c3c3c; border-radius: 4px; padding: 4px 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #007acc; }

QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: #007acc; color: #ffffff; border-color: #007acc; }
QPushButton:pressed { background-color: #005999; }

QTreeWidget, QTreeView, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit, QScrollArea {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #3c3c3c;
    alternate-background-color: #1e1e1e;
    selection-background-color: #2a5080;
    selection-color: #ffffff;
}
QAbstractItemView {
    background-color: #1e1e1e;
    color: #cccccc;
    alternate-background-color: #1e1e1e;
    selection-background-color: #2a5080;
    selection-color: #ffffff;
    outline: 0;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px;
    background-color: #1e1e1e;
    color: #cccccc;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #2a5080;
    color: #ffffff;
}
QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: #2a2d2e;
    color: #cccccc;
}

QHeaderView::section { background-color: #252526; color: #ffffff; border: 1px solid #3c3c3c; padding: 4px; }
QStatusBar { background-color: #252526; color: #cccccc; border-top: 1px solid #3c3c3c; }
QMenuBar { background-color: #2d2d2d; color: #cccccc; }
QMenuBar::item:selected { background-color: #3c3c3c; }
QMenu { background-color: #252526; color: #cccccc; border: 1px solid #3c3c3c; }
QMenu::item:selected { background-color: #04395e; color: #ffffff; }
QSplitter::handle { background-color: #2d2d2d; }
QSplitter::handle:hover { background-color: #007acc; }

QLabel#lbl_info, QLabel#lbl_sec_info { background-color: #252526; color: #4ec9b0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 8px; }
QWidget#tab_action_bar { background-color: #2d2d2d; border-bottom: 1px solid #3c3c3c; }
"""

LIGHT_STYLESHEET = """
* { font-size: 11px; font-weight: normal; color: #1c1c1e; }
QWidget { background-color: #f5f5f7; color: #1c1c1e; }
QMainWindow, QDialog { background-color: #e5e5e7; }
QDockWidget { background-color: #f5f5f7; color: #1c1c1e; }
QDockWidget::title { background-color: #e5e5e7; color: #1c1c1e; padding: 4px; border-bottom: 1px solid #d1d1d6; }
QMainWindow::separator { background-color: #d1d1d6; width: 1px; height: 1px; image: none; }

QTabWidget::pane { border: 1px solid #d1d1d6; background-color: #ffffff; }
QTabBar::tab { background-color: #e5e5e7; color: #3a3a3c; padding: 6px 14px; border: 1px solid #d1d1d6; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background-color: #ffffff; color: #000000; font-weight: bold; border-bottom: 2px solid #007aff; }

QGroupBox { border: 1px solid #d1d1d6; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #007aff; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; color: #007aff; }

QLineEdit, QSpinBox, QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #c7c7cc; border-radius: 4px; padding: 4px 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #007aff; }

QPushButton { background-color: #e5e5e7; color: #1c1c1e; border: 1px solid #c7c7cc; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: #007aff; color: #ffffff; border-color: #007aff; }
QPushButton:pressed { background-color: #0056b3; color: #ffffff; }

QTreeWidget, QTreeView, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit, QScrollArea {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid #d1d1d6;
    alternate-background-color: #ffffff;
    selection-background-color: #4a8fd4;
    selection-color: #ffffff;
}
QAbstractItemView {
    background-color: #ffffff;
    color: #1c1c1e;
    alternate-background-color: #ffffff;
    selection-background-color: #4a8fd4;
    selection-color: #ffffff;
    outline: 0;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px;
    background-color: #ffffff;
    color: #1c1c1e;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #4a8fd4;
    color: #ffffff;
}
QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: #e5e5e7;
    color: #1c1c1e;
}

QHeaderView::section { background-color: #e5e5e7; color: #1c1c1e; border: 1px solid #d1d1d6; padding: 4px; }
QStatusBar { background-color: #e5e5e7; color: #1c1c1e; border-top: 1px solid #d1d1d6; }
QMenuBar { background-color: #e5e5e7; color: #1c1c1e; }
QMenuBar::item:selected { background-color: #d1d1d6; }
QMenu { background-color: #ffffff; color: #1c1c1e; border: 1px solid #d1d1d6; }
QMenu::item:selected { background-color: #2b70c3; color: #ffffff; }
QSplitter::handle { background-color: #d1d1d6; }
QSplitter::handle:hover { background-color: #007aff; }

QLabel#lbl_info, QLabel#lbl_sec_info { background-color: #ffffff; color: #007aff; border: 1px solid #c7c7cc; border-radius: 4px; padding: 8px; }
QWidget#tab_action_bar { background-color: #e5e5e7; border-bottom: 1px solid #d1d1d6; }
"""

OCEAN_STYLESHEET = """
* { font-size: 11px; font-weight: normal; color: #e0e6ed; }
QWidget { background-color: #0d1b2a; color: #e0e6ed; }
QMainWindow, QDialog { background-color: #1b263b; }
QDockWidget { background-color: #0d1b2a; color: #e0e6ed; }
QDockWidget::title { background-color: #1b263b; color: #e0e6ed; padding: 4px; border-bottom: 1px solid #415a77; }
QMainWindow::separator { background-color: #415a77; width: 1px; height: 1px; image: none; }

QTabWidget::pane { border: 1px solid #415a77; background-color: #0d1b2a; }
QTabBar::tab { background-color: #1b263b; color: #a3b18a; padding: 6px 14px; border: 1px solid #415a77; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background-color: #0d1b2a; color: #ffffff; font-weight: bold; border-bottom: 2px solid #778da9; }

QGroupBox { border: 1px solid #415a77; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #778da9; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; color: #778da9; }

QLineEdit, QSpinBox, QComboBox { background-color: #1b263b; color: #ffffff; border: 1px solid #415a77; border-radius: 4px; padding: 4px 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #778da9; }

QPushButton { background-color: #415a77; color: #ffffff; border: 1px solid #778da9; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: #778da9; color: #ffffff; border-color: #778da9; }
QPushButton:pressed { background-color: #1b263b; }

QTreeWidget, QTreeView, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit, QScrollArea {
    background-color: #0d1b2a;
    color: #e0e6ed;
    border: 1px solid #415a77;
    alternate-background-color: #0d1b2a;
    selection-background-color: #415a77;
    selection-color: #ffffff;
}
QAbstractItemView {
    background-color: #0d1b2a;
    color: #e0e6ed;
    alternate-background-color: #0d1b2a;
    selection-background-color: #415a77;
    selection-color: #ffffff;
    outline: 0;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px;
    background-color: #0d1b2a;
    color: #e0e6ed;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #415a77;
    color: #ffffff;
}
QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: #1b263b;
    color: #e0e6ed;
}

QHeaderView::section { background-color: #1b263b; color: #e0e6ed; border: 1px solid #415a77; padding: 4px; }
QStatusBar { background-color: #1b263b; color: #e0e6ed; border-top: 1px solid #415a77; }
QMenuBar { background-color: #1b263b; color: #e0e6ed; }
QMenuBar::item:selected { background-color: #415a77; }
QMenu { background-color: #1b263b; color: #e0e6ed; border: 1px solid #415a77; }
QMenu::item:selected { background-color: #415a77; color: #ffffff; }
QSplitter::handle { background-color: #415a77; }
QSplitter::handle:hover { background-color: #778da9; }

QLabel#lbl_info, QLabel#lbl_sec_info { background-color: #1b263b; color: #778da9; border: 1px solid #415a77; border-radius: 4px; padding: 8px; }
QWidget#tab_action_bar { background-color: #1b263b; border-bottom: 1px solid #415a77; }
"""

FOREST_STYLESHEET = """
* { font-size: 11px; font-weight: normal; color: #e2e8f0; }
QWidget { background-color: #142217; color: #e2e8f0; }
QMainWindow, QDialog { background-color: #1c2a1e; }
QDockWidget { background-color: #142217; color: #e2e8f0; }
QDockWidget::title { background-color: #1c2a1e; color: #e2e8f0; padding: 4px; border-bottom: 1px solid #2d4a34; }
QMainWindow::separator { background-color: #2d4a34; width: 1px; height: 1px; image: none; }

QTabWidget::pane { border: 1px solid #2d4a34; background-color: #142217; }
QTabBar::tab { background-color: #1c2a1e; color: #a3b18a; padding: 6px 14px; border: 1px solid #2d4a34; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background-color: #142217; color: #ffffff; font-weight: bold; border-bottom: 2px solid #52796f; }

QGroupBox { border: 1px solid #2d4a34; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #52796f; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; color: #84a98c; }

QLineEdit, QSpinBox, QComboBox { background-color: #1c2a1e; color: #ffffff; border: 1px solid #2d4a34; border-radius: 4px; padding: 4px 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #52796f; }

QPushButton { background-color: #2d4a34; color: #ffffff; border: 1px solid #3d6849; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: #3d6849; color: #ffffff; border-color: #3d6849; }
QPushButton:pressed { background-color: #1c2a1e; }

QTreeWidget, QTreeView, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit, QScrollArea {
    background-color: #142217;
    color: #e2e8f0;
    border: 1px solid #2d4a34;
    alternate-background-color: #142217;
    selection-background-color: #2d4a34;
    selection-color: #ffffff;
}
QAbstractItemView {
    background-color: #142217;
    color: #e2e8f0;
    alternate-background-color: #142217;
    selection-background-color: #2d4a34;
    selection-color: #ffffff;
    outline: 0;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px;
    background-color: #142217;
    color: #e2e8f0;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #2d4a34;
    color: #ffffff;
}
QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: #1c2a1e;
    color: #e2e8f0;
}

QHeaderView::section { background-color: #1c2a1e; color: #e2e8f0; border: 1px solid #2d4a34; padding: 4px; }
QStatusBar { background-color: #1c2a1e; color: #e2e8f0; border-top: 1px solid #2d4a34; }
QMenuBar { background-color: #1c2a1e; color: #e2e8f0; }
QMenuBar::item:selected { background-color: #2d4a34; }
QMenu { background-color: #1c2a1e; color: #e2e8f0; border: 1px solid #2d4a34; }
QMenu::item:selected { background-color: #2d4a34; color: #ffffff; }
QSplitter::handle { background-color: #2d4a34; }
QSplitter::handle:hover { background-color: #52796f; }

QLabel#lbl_info, QLabel#lbl_sec_info { background-color: #1c2a1e; color: #52796f; border: 1px solid #2d4a34; border-radius: 4px; padding: 8px; }
QWidget#tab_action_bar { background-color: #1c2a1e; border-bottom: 1px solid #2d4a34; }
"""


def get_theme_stylesheet(theme_name: str) -> str:
    name = (theme_name or "Dark").strip()
    if name == "Light":
        return LIGHT_STYLESHEET
    elif name == "Ocean":
        return OCEAN_STYLESHEET
    elif name == "Forest":
        return FOREST_STYLESHEET
    return DARK_STYLESHEET


# Per-theme palette values used to override the system QPalette for item views
_THEME_PALETTE = {
    "Dark":   {"bg": "#1e1e1e", "text": "#cccccc", "sel_bg": "#2a5080", "sel_fg": "#ffffff", "alt": "#1e1e1e"},
    "Light":  {"bg": "#ffffff", "text": "#1c1c1e", "sel_bg": "#4a8fd4", "sel_fg": "#ffffff", "alt": "#ffffff"},
    "Ocean":  {"bg": "#0d1b2a", "text": "#e0e6ed", "sel_bg": "#415a77", "sel_fg": "#ffffff", "alt": "#0d1b2a"},
    "Forest": {"bg": "#142217", "text": "#e2e8f0", "sel_bg": "#2d4a34", "sel_fg": "#ffffff", "alt": "#142217"},
}


def apply_theme(theme_name: str):
    """
    Applies theme stylesheet across active QApplication instance in real time.
    Also forces QPalette on all QAbstractItemView widgets to prevent the system
    highlight color (blue on KDE/GNOME) from bleeding through transparent QSS backgrounds.
    """
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtWidgets import QAbstractItemView

    app = QApplication.instance()
    if not app:
        return

    name = (theme_name or "Dark").strip()
    app.setStyleSheet(get_theme_stylesheet(name))

    palette_cfg = _THEME_PALETTE.get(name, _THEME_PALETTE["Dark"])
    bg_color      = QColor(palette_cfg["bg"])
    text_color    = QColor(palette_cfg["text"])
    sel_bg_color  = QColor(palette_cfg["sel_bg"])
    sel_fg_color  = QColor(palette_cfg["sel_fg"])
    alt_color     = QColor(palette_cfg["alt"])

    # Force QPalette on every QAbstractItemView (tree, list, table) in the app
    for widget in app.allWidgets():
        if isinstance(widget, QAbstractItemView):
            pal = widget.palette()
            pal.setColor(QPalette.ColorRole.Base,            bg_color)
            pal.setColor(QPalette.ColorRole.AlternateBase,   alt_color)
            pal.setColor(QPalette.ColorRole.Text,            text_color)
            pal.setColor(QPalette.ColorRole.Highlight,       sel_bg_color)
            pal.setColor(QPalette.ColorRole.HighlightedText, sel_fg_color)
            widget.setPalette(pal)
            # Also force the viewport palette for complete coverage
            vp = widget.viewport()
            if vp:
                vp_pal = vp.palette()
                vp_pal.setColor(QPalette.ColorRole.Base,   bg_color)
                vp_pal.setColor(QPalette.ColorRole.Window, bg_color)
                vp.setPalette(vp_pal)
                vp.setAutoFillBackground(True)

