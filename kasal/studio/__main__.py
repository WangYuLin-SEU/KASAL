from __future__ import annotations
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description='KASAL Studio — independent desktop preview')
    parser.add_argument('path', nargs='?', type=Path, help='Mesh file or model directory')
    args = parser.parse_args()
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QSettings
        from .theme import STYLE
        from .window import StudioWindow
    except ImportError as exc:
        parser.exit(1, f'Studio requires its optional desktop dependencies: {exc}\nRun: python -m pip install -r requirements/studio.txt\n')
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    settings = QSettings('KASAL', 'StudioPreview')
    app.setStyleSheet(STYLE.replace('font-size: 13px;', f'font-size: {int(settings.value("font_size", 13))}px;'))
    window = StudioWindow(args.path, settings=settings)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
