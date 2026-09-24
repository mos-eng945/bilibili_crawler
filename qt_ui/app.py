"""Qt application entry point."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from bilibili_api import BASE_DIR
from qt_ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Bilibili 数据采集器")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(BASE_DIR / "assets" / "app-icon.svg")))

    window = MainWindow()
    window.show()
    return app.exec()
