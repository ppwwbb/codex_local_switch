"""
代理控制标签页
- 监听地址/端口配置
- 启动/停止代理按钮
- 实时日志输出
- 使用提示（Codex 如何配置）
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QTextEdit, QGroupBox, QFormLayout
)

from gui.log_widget import LogWidget


class ProxyTab(QWidget):
    proxy_toggled = pyqtSignal(bool)  # started
    config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 代理配置组
        config_group = QGroupBox("代理监听配置")
        config_layout = QFormLayout(config_group)

        self.host_edit = QLineEdit("127.0.0.1")
        config_layout.addRow("监听地址:", self.host_edit)

        self.port_edit = QLineEdit("8317")
        config_layout.addRow("监听端口:", self.port_edit)
        main_layout.addWidget(config_group)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 启动代理")
        self.start_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; padding: 10px; font-size: 14px; }")
        self.start_btn.clicked.connect(self._toggle_proxy)
        btn_layout.addWidget(self.start_btn)

        self.status_label = QLabel("状态: 未运行")
        self.status_label.setStyleSheet("color: #999;")
        btn_layout.addWidget(self.status_label)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 使用提示
        tip_group = QGroupBox("使用提示")
        tip_layout = QVBoxLayout(tip_group)
        tip_text = QTextEdit()
        tip_text.setReadOnly(True)
        tip_text.setMaximumHeight(120)
        tip_text.setPlainText(
            "1. 在 Provider 标签页配置好 Kimi Code 的 API Key 和 Base URL\n"
            "2. 点击「启动代理」后，代理会监听上方配置的地址\n"
            "3. 在 Codex 或 Claude Code 中设置环境变量:\n"
            "   ANTHROPIC_BASE_URL=http://127.0.0.1:8317/v1\n"
            "   ANTHROPIC_AUTH_TOKEN=任意值（代理会自动替换为真实 Key）\n"
            "4. 若 Codex 使用 OpenAI 协议，则设置:\n"
            "   OPENAI_BASE_URL=http://127.0.0.1:8317/v1"
        )
        tip_layout.addWidget(tip_text)
        main_layout.addWidget(tip_group)

        # 日志区域
        main_layout.addWidget(QLabel("运行日志:"))
        self.log_widget = LogWidget()
        main_layout.addWidget(self.log_widget)

    def load_config(self, host: str, port: int) -> None:
        self.host_edit.setText(host)
        self.port_edit.setText(str(port))

    def get_host(self) -> str:
        return self.host_edit.text().strip() or "127.0.0.1"

    def get_port(self) -> int:
        try:
            return int(self.port_edit.text().strip())
        except ValueError:
            return 8317

    def _toggle_proxy(self) -> None:
        self.proxy_toggled.emit(True)

    def set_running(self, running: bool) -> None:
        if running:
            self.start_btn.setText("⏹ 停止代理")
            self.start_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; padding: 10px; font-size: 14px; }")
            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.host_edit.setEnabled(False)
            self.port_edit.setEnabled(False)
        else:
            self.start_btn.setText("▶ 启动代理")
            self.start_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; padding: 10px; font-size: 14px; }")
            self.status_label.setText("状态: 未运行")
            self.status_label.setStyleSheet("color: #999;")
            self.host_edit.setEnabled(True)
            self.port_edit.setEnabled(True)

    def log(self, level: str, message: str) -> None:
        self.log_widget.log(level, message)
