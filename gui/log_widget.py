"""
日志输出组件，基于 tkinter，带级别过滤和自动滚动
"""
import tkinter as tk
from tkinter import ttk


class LogWidget(tk.Frame):
    """带过滤和清除功能的日志面板"""

    LEVEL_COLORS = {
        "DEBUG": "#808080",
        "INFO": "#0066cc",
        "WARNING": "#ff9900",
        "ERROR": "#cc0000",
    }

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._init_ui()

    def _init_ui(self):
        # 顶部工具栏
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 4))

        tk.Label(toolbar, text="日志级别:").pack(side=tk.LEFT)
        self.level_var = tk.StringVar(value="INFO")
        self.level_combo = ttk.Combobox(
            toolbar, textvariable=self.level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            state="readonly", width=10
        )
        self.level_combo.pack(side=tk.LEFT, padx=(4, 8))

        self.clear_btn = tk.Button(toolbar, text="清空", command=self.clear)
        self.clear_btn.pack(side=tk.LEFT)

        # 日志文本框
        self.text = tk.Text(self, wrap=tk.WORD, state=tk.DISABLED, height=12)
        self.text.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.text, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def log(self, level, message):
        """追加日志"""
        # 级别过滤
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if levels.index(level) < levels.index(self.level_var.get()):
            return

        color = self.LEVEL_COLORS.get(level, "#000000")
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, f"[{level}] ", (level,))
        self.text.insert(tk.END, f"{message}\n")
        self.text.tag_config(level, foreground=color)
        self.text.see(tk.END)
        self.text.config(state=tk.DISABLED)

    def clear(self):
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)
