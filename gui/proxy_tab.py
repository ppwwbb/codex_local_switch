"""
代理控制标签页（tkinter 版本）
- 监听地址/端口配置
- 启动/停止代理按钮
- 实时日志输出
- 使用提示
"""
import tkinter as tk
from tkinter import ttk

from gui.log_widget import LogWidget


class ProxyTab(tk.Frame):
    def __init__(self, master=None, on_toggle=None, on_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_toggle = on_toggle
        self.on_change = on_change
        self._init_ui()

    def _init_ui(self):
        pad = {"padx": 12, "pady": 6}

        # 代理配置
        config_frame = tk.LabelFrame(self, text="代理监听配置", padx=10, pady=10)
        config_frame.pack(fill=tk.X, **pad)

        tk.Label(config_frame, text="监听地址:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(config_frame, textvariable=self.host_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=(8, 0))

        tk.Label(config_frame, text="监听端口:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.port_var = tk.StringVar(value="8317")
        tk.Entry(config_frame, textvariable=self.port_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=(8, 0))

        # 控制按钮
        ctrl_frame = tk.Frame(self)
        ctrl_frame.pack(fill=tk.X, **pad)

        self.start_btn = tk.Button(
            ctrl_frame, text="▶ 启动代理", bg="#28a745", fg="white",
            font=("Arial", 11), padx=12, pady=6, command=self._toggle
        )
        self.start_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(ctrl_frame, text="状态: 未运行", fg="#999")
        self.status_label.pack(side=tk.LEFT, padx=(12, 0))

        # 使用提示
        tip_frame = tk.LabelFrame(self, text="使用提示", padx=10, pady=10)
        tip_frame.pack(fill=tk.X, **pad)

        tip_text = tk.Text(tip_frame, wrap=tk.WORD, height=6, state=tk.DISABLED)
        tip_text.pack(fill=tk.X)
        tip_text.config(state=tk.NORMAL)
        tip_text.insert("1.0",
            "1. 在 Provider 标签页配置好 Kimi Code 的 API Key 和 Base URL\n"
            "2. 点击「启动代理」后，代理会监听上方配置的地址\n"
            "3. 在 Codex 或 Claude Code 中设置环境变量:\n"
            "   ANTHROPIC_BASE_URL=http://127.0.0.1:8317/v1\n"
            "   ANTHROPIC_AUTH_TOKEN=任意值（代理会自动替换为真实 Key）\n"
            "4. 若 Codex 使用 OpenAI 协议，则设置:\n"
            "   OPENAI_BASE_URL=http://127.0.0.1:8317/v1"
        )
        tip_text.config(state=tk.DISABLED)

        # 日志
        tk.Label(self, text="运行日志:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=(12, 0))
        self.log_widget = LogWidget(self)
        self.log_widget.pack(fill=tk.BOTH, expand=True, **pad)

    def load_config(self, host, port):
        self.host_var.set(host)
        self.port_var.set(str(port))

    def get_host(self):
        return self.host_var.get().strip() or "127.0.0.1"

    def get_port(self):
        try:
            return int(self.port_var.get().strip())
        except ValueError:
            return 8317

    def _toggle(self):
        if self.on_toggle:
            self.on_toggle()

    def set_running(self, running):
        if running:
            self.start_btn.config(text="⏹ 停止代理", bg="#dc3545")
            self.status_label.config(text="状态: 运行中", fg="#28a745", font=("Arial", 9, "bold"))
            self.host_var.trace_add("write", lambda *args: None)  # tk.Entry 没有 setEnabled，直接 disable
            for w in [self.host_var, self.port_var]:
                pass  # tkinter StringVar 不能直接 disable widget，需要在主窗口控制
        else:
            self.start_btn.config(text="▶ 启动代理", bg="#28a745")
            self.status_label.config(text="状态: 未运行", fg="#999", font=("Arial", 9))

    def set_entries_state(self, state):
        """由主窗口调用，启用或禁用输入框"""
        for child in self.winfo_children():
            if isinstance(child, tk.LabelFrame) and child.cget("text") == "代理监听配置":
                for widget in child.winfo_children():
                    if isinstance(widget, tk.Entry):
                        widget.config(state=state)

    def log(self, level, message):
        self.log_widget.log(level, message)
