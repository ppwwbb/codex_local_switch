"""
主窗口（customtkinter 现代化版本）
整合 Provider 配置与代理控制
"""
import sys

# Windows 高 DPI 适配，必须在创建窗口前调用
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import customtkinter as ctk
from tkinter import messagebox

from config import AppConfig, save_config, load_config
from proxy_server import ProxyServer
from gui.provider_tab import ProviderTab
from gui.proxy_tab import ProxyTab

# 设置 customtkinter 默认主题
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class MainWindow:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("LocalSwitch - API 代理")
        self.root.geometry("1000x720")
        self.root.minsize(900, 600)
        self.root.configure(fg_color="#F5F5F7")

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
        # 顶部标题栏
        self._build_header()

        # TabView 标签页
        self.tabview = ctk.CTkTabview(
            self.root,
            fg_color="transparent",
            segmented_button_fg_color="#FFFFFF",
            segmented_button_selected_color="#FF6B35",
            segmented_button_selected_hover_color="#E55A2B",
            segmented_button_unselected_color="#F0F0F0",
            segmented_button_unselected_hover_color="#E8E8E8",
            text_color="#333333",
            corner_radius=12,
            border_width=0,
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Provider 标签页
        self.provider_tab = ProviderTab(self.tabview.add("Provider 配置"), on_change=self._save_config)

        # 代理控制标签页
        self.proxy_tab = ProxyTab(self.tabview.add("代理控制"), on_toggle=self._toggle_proxy, on_change=self._save_config)

        # 状态栏
        self.status_var = ctk.StringVar(value="就绪")
        self.status_bar = ctk.CTkLabel(
            self.root,
            textvariable=self.status_var,
            font=("Microsoft YaHei", 11),
            text_color="#888888",
            fg_color="#FFFFFF",
            corner_radius=0,
            anchor="w",
            height=32,
        )
        self.status_bar.pack(side="bottom", fill="x", padx=0, pady=0)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color="#FFFFFF", height=56, corner_radius=0)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="LocalSwitch",
            font=("Microsoft YaHei", 18, "bold"),
            text_color="#1A1A1A",
        )
        title.pack(side="left", padx=(20, 8), pady=8)

        subtitle = ctk.CTkLabel(
            header,
            text="API 协议转换代理",
            font=("Microsoft YaHei", 12),
            text_color="#888888",
        )
        subtitle.pack(side="left", pady=8)

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
            self.status_var.set(f"代理已启动: http://{self.proxy.host}:{self.proxy.port}")
            self.proxy_tab.log("INFO", f"代理启动成功，监听 http://{self.proxy.host}:{self.proxy.port}")
            self.proxy_tab.log("INFO", f"当前上游: {provider.name} ({provider.base_url})")
        except Exception as e:
            messagebox.showerror("启动失败", f"代理启动异常: {str(e)}")
            self.proxy_tab.log("ERROR", f"代理启动失败: {str(e)}")

    def _stop_proxy(self):
        self.proxy.stop()
        self.proxy_tab.set_running(False)
        self.status_var.set("代理已停止")
        self.proxy_tab.log("INFO", "代理已停止")

    def _check_status(self):
        is_running = self.proxy.is_running()
        self.proxy_tab.set_running(is_running)
        self.root.after(1000, self._check_status)

    def _on_proxy_log(self, level, message):
        self.root.after(0, lambda: self.proxy_tab.log(level, message))

    def _on_close(self):
        self._save_config()
        if self.proxy.is_running():
            self.proxy.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_app():
    app = MainWindow()
    app.run()
