# -*- coding: utf-8 -*-
"""兼容入口：仍可用 `python name_picker.py` 启动，实现全部在 name_picker/ 包内。"""
import sys

from PyQt5.QtWidgets import QApplication

from name_picker.main_window import NamePickerUI


def main():
    app = QApplication(sys.argv)

    if '--version' in app.arguments():
        from name_picker import __version__
        print(f"v{__version__}")
        sys.exit(0)

    app.setQuitOnLastWindowClosed(False)
    w = NamePickerUI()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()