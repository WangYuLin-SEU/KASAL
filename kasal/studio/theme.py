"""Light desktop palette and small, consistent vector icons."""
from pathlib import Path
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

STYLE = '''
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; font-size: 13px; color: #273449; }
QMainWindow, QDialog { background: #f5f7fa; }
QFrame#header { background: white; border-bottom: 1px solid #dfe5ed; }
QFrame#sidebar, QFrame#inspector { background: white; }
QFrame#viewportHeader, QFrame#viewTools { background: #f9fbfd; border-bottom: 1px solid #e3e9f0; }
QFrame#footer { background: white; border-top: 1px solid #dfe5ed; }
QLabel#brand { font-size: 22px; font-weight: 700; color: #172943; }
QLabel#eyebrow { font-size: 10px; font-weight: 700; color: #8492a6; letter-spacing: 2px; }
QLabel#title { font-size: 17px; font-weight: 650; color: #172943; }
QLabel#section { font-size: 13px; font-weight: 650; color: #263a54; }
QLabel#muted { color: #7b889a; font-size: 12px; }
QLabel#hint { color: #7b889a; font-size: 11px; }
QLabel#badge { background: #edf4ff; color: #3269bd; border-radius: 5px; padding: 4px 9px; font-size: 11px; }
QLabel#success { background: #edf8f3; color: #238264; border-radius: 5px; padding: 5px 8px; font-size: 12px; }
QLabel#error { color: #b54747; background: #fff1ef; border-radius: 6px; padding: 8px; }
QPushButton, QToolButton { background: white; border: 1px solid #dfe5ed; border-radius: 6px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #f0f5fc; border-color: #afc4e2; }
QPushButton:pressed, QToolButton:pressed { background: #e4edfa; }
QPushButton:disabled, QToolButton:disabled { color: #aeb7c5; background: #f6f8fb; border-color: #edf0f4; }
QPushButton#primary { background: #326bd6; border-color: #326bd6; color: white; font-weight: 600; padding: 10px 16px; }
QPushButton#primary:hover { background: #265bc1; }
QPushButton#primary:disabled { background: #b5c8e8; border-color: #b5c8e8; }
QPushButton#subtle { border-color: transparent; background: transparent; color: #61718a; }
QPushButton#subtle:hover { background: #edf3fa; }
QPushButton#danger { color: #b54747; border-color: #f0d3d0; }
QPushButton:checked { color: #2d65c8; background: #eaf1ff; border-color: #b5cdf2; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { border: 1px solid #dde4ed; border-radius: 6px; padding: 7px 9px; background: #fbfcfe; min-height: 18px; selection-background-color: #dce9ff; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #6d99df; background: white; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: #f6f8fb; color: #a5afbe; }
QComboBox::drop-down { border: none; width: 23px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #dfe5ed; selection-background-color: #eaf1ff; selection-color: #235ac0; padding: 5px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 18px; border: none; }
QListWidget { border: none; background: white; outline: none; padding: 4px; }
QListWidget::item { padding: 12px 10px; border-radius: 7px; margin: 3px 1px; color: #516078; }
QListWidget::item:selected { background: #eaf1ff; color: #245cb9; }
QListWidget::item:hover:!selected { background: #f4f7fb; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #c8d3e2; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #326bd6; border-color: #326bd6; }
QProgressBar { background: #eaf0f8; border: none; border-radius: 3px; min-height: 5px; max-height: 5px; }
QProgressBar::chunk { background: #3974df; border-radius: 3px; }
QSlider::groove:horizontal { height: 4px; background: #e2e9f2; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #7ea2dd; border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -5px 0; background: #326bd6; border-radius: 6px; }
QScrollArea { border: none; background: white; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 3px 0; }
QScrollBar::handle:vertical { background: #d3dce8; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #e4e9f0; width: 1px; }
QMenu { background: white; border: 1px solid #dfe5ed; padding: 5px; }
QMenu::item { padding: 8px 22px; border-radius: 4px; }
QMenu::item:selected { background: #eaf1ff; }
QToolTip { background: #24364f; color: white; border: none; padding: 6px; }
'''

_assets = Path(__file__).with_name('assets')
STYLE += '\nQComboBox::down-arrow { width: 12px; height: 12px; image: url("' + (_assets / 'chevron-down.svg').as_posix() + '"); }'
STYLE += '\nQCheckBox::indicator:checked { image: url("' + (_assets / 'check.svg').as_posix() + '"); }'

PATHS = {
    'folder': '<path d="M3 7V5h6l2 2h10v12H3Z"/>',
    'cube': '<path d="m12 3 9 5v9l-9 5-9-5V8Z M3 8l9 5 9-5 M12 13v9 M7.5 5.5l9 5v4"/>',
    'play': '<path d="m8 5 11 7-11 7Z"/>',
    'batch': '<path d="m13 7 8 5-8 5Z M4 5v14 M8 5v14"/>',
    'settings': '<path d="M4 7h16 M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
    'fit': '<path d="M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
    'camera': '<path d="M3 7h5l2-3h4l2 3h5v13H3Z"/><circle cx="12" cy="13" r="4"/>',
    'export': '<path d="M5 14v6h14v-6 M12 16V3 M7 8l5-5 5 5"/>',
    'left': '<path d="m14 6-6 6 6 6"/>',
    'right': '<path d="m10 6 6 6-6 6"/>',
    'help': '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 17h.01"/>',
    'more': '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    'refresh': '<path d="M20 9a8 8 0 1 0 0 6 M20 3v6h-6"/>',
    'stop': '<rect x="6" y="6" width="12" height="12" rx="1"/>',
}


def icon(name: str, color: str = '#657995', size: int = 20) -> QIcon:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
