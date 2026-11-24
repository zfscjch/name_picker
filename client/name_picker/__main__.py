# -*- coding: utf-8 -*-
"""包入口：python -m name_picker"""
import sys

from PyQt5.QtWidgets import QApplication

from .main_window import NamePickerUI


def main():
    app = QApplication(sys.argv)

    if '--version' in app.arguments():
        from . import __version__
        print(f"v{__version__}")
        sys.exit(0)

    app.setQuitOnLastWindowClosed(False)
    w = NamePickerUI()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()