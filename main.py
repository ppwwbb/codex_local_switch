#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LocalSwitch 入口文件
启动 tkinter GUI 和后台代理服务器。

使用方式:
    python main.py

环境要求:
    Python 3.7+
    依赖见 requirements.txt（GUI 使用内置 tkinter，无需 PyQt）
"""
from gui.main_window import run

if __name__ == "__main__":
    run()
