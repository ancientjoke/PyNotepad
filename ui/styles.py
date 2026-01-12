"""
Application Styles

Dark theme stylesheet for the PDF viewer application.
"""

DARK_STYLE = """
/* Main Window */
QMainWindow {
    background-color: #1e1e1e;
    color: #d4d4d4;
}

/* Menu Bar */
QMenuBar {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border-bottom: 1px solid #3c3c3c;
    padding: 2px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #3c3c3c;
}

QMenuBar::item:pressed {
    background-color: #0078d4;
}

/* Menus */
QMenu {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0078d4;
}

QMenu::separator {
    height: 1px;
    background-color: #3c3c3c;
    margin: 4px 8px;
}

/* Toolbar */
QToolBar {
    background-color: #2d2d2d;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    padding: 4px;
    spacing: 4px;
}

QToolBar::separator {
    width: 1px;
    background-color: #3c3c3c;
    margin: 4px 8px;
}

QToolButton {
    background-color: transparent;
    color: #d4d4d4;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 24px;
}

QToolButton:hover {
    background-color: #3c3c3c;
}

QToolButton:pressed {
    background-color: #0078d4;
}

QToolButton:checked {
    background-color: #0078d4;
}

/* Tab Widget */
QTabWidget::pane {
    border: none;
    background-color: #1e1e1e;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #3c3c3c;
    color: #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #383838;
}

QTabBar::close-button {
    image: url(close.png);
    subcontrol-position: right;
}

QTabBar::close-button:hover {
    background-color: #c42b1c;
    border-radius: 2px;
}

/* Scroll Bars */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #5a5a5a;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #787878;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #5a5a5a;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #787878;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Splitter */
QSplitter::handle {
    background-color: #3c3c3c;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #0078d4;
}

/* Tree Widget */
QTreeWidget {
    background-color: #252526;
    color: #d4d4d4;
    border: none;
    outline: none;
}

QTreeWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}

QTreeWidget::item:hover {
    background-color: #2a2d2e;
}

QTreeWidget::item:selected {
    background-color: #0078d4;
}

QTreeWidget::branch {
    background-color: transparent;
}

/* List Widget */
QListWidget {
    background-color: #252526;
    color: #d4d4d4;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #2a2d2e;
}

QListWidget::item:selected {
    background-color: #0078d4;
}

/* Line Edit */
QLineEdit {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #5a5a5a;
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: #0078d4;
}

QLineEdit:focus {
    border-color: #0078d4;
}

QLineEdit:hover {
    border-color: #6a6a6a;
}

/* Combo Box */
QComboBox {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #5a5a5a;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 80px;
}

QComboBox:hover {
    border-color: #6a6a6a;
}

QComboBox:focus {
    border-color: #0078d4;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    selection-background-color: #0078d4;
}

/* Spin Box */
QSpinBox {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #5a5a5a;
    border-radius: 4px;
    padding: 4px 8px;
}

QSpinBox:hover {
    border-color: #6a6a6a;
}

QSpinBox:focus {
    border-color: #0078d4;
}

/* Push Button */
QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1a86d8;
}

QPushButton:pressed {
    background-color: #005a9e;
}

QPushButton:disabled {
    background-color: #4a4a4a;
    color: #8a8a8a;
}

/* Status Bar */
QStatusBar {
    background-color: #007acc;
    color: #ffffff;
    border: none;
}

QStatusBar::item {
    border: none;
}

QStatusBar QLabel {
    color: #ffffff;
    padding: 2px 8px;
}

/* Frame */
QFrame {
    background-color: #2d2d2d;
    border: none;
}

/* Labels */
QLabel {
    color: #d4d4d4;
}

/* Message Box */
QMessageBox {
    background-color: #2d2d2d;
    color: #d4d4d4;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* Input Dialog */
QInputDialog {
    background-color: #2d2d2d;
    color: #d4d4d4;
}

/* Tooltip */
QToolTip {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px 8px;
}

/* Dialog */
QDialog {
    background-color: #2d2d2d;
    color: #d4d4d4;
}

/* Group Box */
QGroupBox {
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""

def apply_dark_theme(app):
    """Apply dark theme to the application."""
    app.setStyleSheet(DARK_STYLE)
