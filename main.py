#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LocalSwitch 入口文件（Tauri + Web 前端版本）
启动 FastAPI 后端服务（端口 8318），供前端页面调用。

使用方式:
    python main.py

环境要求:
    Python 3.8+
    依赖见 requirements.txt
"""
import sys
import os

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.api_server import run_api_server

if __name__ == "__main__":
    print("=" * 50)
    print("LocalSwitch Python Backend")
    print("API: http://127.0.0.1:8318")
    print("Proxy: http://127.0.0.1:8317")
    print("=" * 50)
    run_api_server(host="127.0.0.1", port=8318)
