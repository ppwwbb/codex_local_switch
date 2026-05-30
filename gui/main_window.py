"""
主窗口，整合 Provider 配置与代理控制
"""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QStatusBar, QMessageBox
)

from config import AppConfig, Provider, save_config, load_config
from proxy_server import ProxyServer
from gui.provider_tab import ProviderTab
from gui.proxy_tab import ProxyTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalSwitch - API 代理")
        self.setMinimumSize(800, 600)

        self.config = load_config()
        self.proxy = ProxyServer(
            host=self.config.listen_host,
            port=self.config.listen_port,
        )
        self.proxy.set_log_callback(self._on_proxy_log)

        self._init_ui()
        self._apply_config()

        # 定时检查代理状态
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_proxy_status)
        self._timer.start(1000)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        # Provider 标签页
        self.provider_tab = ProviderTab()
        self.provider_tab.config_changed.connect(self._save_config)
        self.tabs.addTab(self.provider_tab, "Provider 配置")

        # 代理控制标签页
        self.proxy_tab = ProxyTab()
        self.proxy_tab.proxy_toggled.connect(self._toggle_proxy)
        self.proxy_tab.config_changed.connect(self._save_config)
        self.tabs.addTab(self.proxy_tab, "代理控制")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        self.setStatusBar(self.status_bar)

    def _apply_config(self):
        """将加载的配置应用到界面"""
        self.provider_tab.load_providers(self.config.providers, self.config.current_provider_id)
        self.proxy_tab.load_config(self.config.listen_host, self.config.listen_port)

        # 如果有当前 provider，设置到代理
        provider = self.config.get_current_provider()
        if provider:
            self.proxy.set_provider(provider)

    def _save_config(self):
        """从界面收集配置并持久化"""
        self.config.providers = self.provider_tab.get_providers()
        self.config.current_provider_id = self.provider_tab.get_current_provider_id()
        self.config.listen_host = self.proxy_tab.get_host()
        self.config.listen_port = self.proxy_tab.get_port()
        save_config(self.config)
        self.status_bar.showMessage("配置已保存", 3000)

    def _toggle_proxy(self):
        if self.proxy.is_running():
            self._stop_proxy()
        else:
            self._start_proxy()

    def _start_proxy(self):
        # 先保存当前配置
        self._save_config()

        provider = self.config.get_current_provider()
        if not provider:
            QMessageBox.warning(self, "启动失败", "请先配置至少一个 Provider")
            return
        if not provider.api_key:
            QMessageBox.warning(self, "启动失败", "当前 Provider 的 API Key 为空，请检查配置")
            return
        if not provider.base_url:
            QMessageBox.warning(self, "启动失败", "当前 Provider 的 Base URL 为空，请检查配置")
            return

        # 更新代理参数
        self.proxy.host = self.config.listen_host
        self.proxy.port = self.config.listen_port
        self.proxy.set_provider(provider)

        try:
            self.proxy.start()
            self.proxy_tab.set_running(True)
            self.status_bar.showMessage(
                f"代理已启动: http://{self.proxy.host}:{self.proxy.port}", 5000
            )
            self.proxy_tab.log("INFO", f"代理启动成功，监听 http://{self.proxy.host}:{self.proxy.port}")
            self.proxy_tab.log("INFO", f"当前上游: {provider.name} ({provider.base_url})")
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"代理启动异常: {str(e)}")
            self.proxy_tab.log("ERROR", f"代理启动失败: {str(e)}")

    def _stop_proxy(self):
        self.proxy.stop()
        self.proxy_tab.set_running(False)
        self.status_bar.showMessage("代理已停止", 3000)
        self.proxy_tab.log("INFO", "代理已停止")

    def _check_proxy_status(self):
        """定时检查代理是否仍在运行"""
        is_running = self.proxy.is_running()
        # 如果界面显示运行中但实际已停止，同步状态
        if not is_running and self.start_btn_text_is_stop():
            self.proxy_tab.set_running(False)
            self.proxy_tab.log("WARNING", "代理意外停止")

    def start_btn_text_is_stop(self):
        # 简单判断代理标签页按钮状态
        return "停止" in self.proxy_tab.start_btn.text()

    def _on_proxy_log(self, level: str, message: str):
        """代理日志回调，通过 Qt 信号线程安全地写入 GUI"""
        # QTimer.singleShot 确保在主线程执行
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.proxy_tab.log(level, message))

    def closeEvent(self, event):
        """关闭窗口时停止代理并保存配置"""
        self._save_config()
        if self.proxy.is_running():
            self.proxy.stop()
        event.accept()
