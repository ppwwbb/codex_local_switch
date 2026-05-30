#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LocalSwitch 入口文件
启动 PyQt5 GUI 和后台代理服务器。

使用方式:
    python main.py

环境要求:
    Python 3.7+
    依赖见 requirements.txt
"""
import sys

from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LocalSwitch")
    app.setApplicationDisplayName("LocalSwitch")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
