"""
主窗口（tkinter 版本），整合 Provider 配置与代理控制
"""
import tkinter as tk
from tkinter import ttk, messagebox

from config import AppConfig, save_config, load_config
from proxy_server import ProxyServer
from gui.provider_tab import ProviderTab
from gui.proxy_tab import ProxyTab


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LocalSwitch - API 代理")
        self.root.geometry("860x640")
        self.root.minsize(700, 500)

        self.config = load_config()
        self.proxy = ProxyServer(
            host=self.config.listen_host,
            port=self.config.listen_port,
        )
        self.proxy.set_log_callback(self._on_proxy_log)

        self._init_ui()
        self._apply_config()

        # 定时检查代理状态
        self._check_status()

    def _init_ui(self):
        # Notebook 标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Provider 标签页
        self.provider_tab = ProviderTab(self.notebook, on_change=self._save_config)
        self.notebook.add(self.provider_tab, text="Provider 配置")

        # 代理控制标签页
        self.proxy_tab = ProxyTab(self.notebook, on_toggle=self._toggle_proxy, on_change=self._save_config)
        self.notebook.add(self.proxy_tab, text="代理控制")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_config(self):
        self.provider_tab.load_providers(self.config.providers, self.config.current_provider_id)
        self.proxy_tab.load_config(self.config.listen_host, self.config.listen_port)
        provider = self.config.get_current_provider()
        if provider:
            self.proxy.set_provider(provider)

    def _save_config(self):
        self.config.providers = self.provider_tab.get_providers()
        self.config.current_provider_id = self.provider_tab.get_current_provider_id()
        self.config.listen_host = self.proxy_tab.get_host()
        self.config.listen_port = self.proxy_tab.get_port()
        save_config(self.config)
        self.status_var.set("配置已保存")
        self.root.after(3000, lambda: self.status_var.set("就绪"))

    def _toggle_proxy(self):
        if self.proxy.is_running():
            self._stop_proxy()
        else:
            self._start_proxy()

    def _start_proxy(self):
        self._save_config()

        provider = self.config.get_current_provider()
        if not provider:
            messagebox.showwarning("启动失败", "请先配置至少一个 Provider")
            return
        if not provider.api_key:
            messagebox.showwarning("启动失败", "当前 Provider 的 API Key 为空，请检查配置")
            return
        if not provider.base_url:
            messagebox.showwarning("启动失败", "当前 Provider 的 Base URL 为空，请检查配置")
            return

        self.proxy.host = self.config.listen_host
        self.proxy.port = self.config.listen_port
        self.proxy.set_provider(provider)

        try:
            self.proxy.start()
            self.proxy_tab.set_running(True)
            self.proxy_tab.set_entries_state("disabled")
            self.status_var.set(f"代理已启动: http://{self.proxy.host}:{self.proxy.port}")
            self.proxy_tab.log("INFO", f"代理启动成功，监听 http://{self.proxy.host}:{self.proxy.port}")
            self.proxy_tab.log("INFO", f"当前上游: {provider.name} ({provider.base_url})")
        except Exception as e:
            messagebox.showerror("启动失败", f"代理启动异常: {str(e)}")
            self.proxy_tab.log("ERROR", f"代理启动失败: {str(e)}")

    def _stop_proxy(self):
        self.proxy.stop()
        self.proxy_tab.set_running(False)
        self.proxy_tab.set_entries_state("normal")
        self.status_var.set("代理已停止")
        self.proxy_tab.log("INFO", "代理已停止")

    def _check_status(self):
        """定时检查代理状态"""
        is_running = self.proxy.is_running()
        # 如果界面显示运行中但实际已停止
        if not is_running and self.proxy_tab.start_btn.cget("text") == "⏹ 停止代理":
            self.proxy_tab.set_running(False)
            self.proxy_tab.set_entries_state("normal")
            self.proxy_tab.log("WARNING", "代理意外停止")
        self.root.after(1000, self._check_status)

    def _on_proxy_log(self, level, message):
        """代理日志回调"""
        # tkinter 不是线程安全的，需要用 after 切换到主线程
        self.root.after(0, lambda: self.proxy_tab.log(level, message))

    def _on_close(self):
        self._save_config()
        if self.proxy.is_running():
            self.proxy.stop()
        self.root.destroy()


def run():
    root = tk.Tk()
    root.option_add("*Font", "Arial 10")
    app = MainWindow(root)
    root.mainloop()
