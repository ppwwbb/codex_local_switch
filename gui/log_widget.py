"""
日志输出组件（customtkinter 现代化版本）
深色主题日志面板，带级别过滤和自动滚动
"""
import customtkinter as ctk


class LogWidget(ctk.CTkFrame):
    """带过滤和清除功能的日志面板"""

    LEVEL_COLORS = {
        "DEBUG": "#888888",
        "INFO": "#4FC3F7",
        "WARNING": "#FFB74D",
        "ERROR": "#EF5350",
    }

    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color="#1E1E2E", corner_radius=12, **kwargs)
        self._init_ui()

    def _init_ui(self):
        # 顶部工具栏
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            toolbar,
            text="日志级别:",
            font=("Microsoft YaHei", 11),
            text_color="#AAAAAA",
        ).pack(side="left")

        self.level_var = ctk.StringVar(value="INFO")
        self.level_combo = ctk.CTkComboBox(
            toolbar,
            variable=self.level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=100,
            height=28,
            font=("Microsoft YaHei", 11),
            dropdown_font=("Microsoft YaHei", 11),
            fg_color="#2D2D44",
            border_color="#3D3D5C",
            text_color="#FFFFFF",
            dropdown_fg_color="#2D2D44",
            dropdown_text_color="#FFFFFF",
            dropdown_hover_color="#3D3D5C",
            corner_radius=6,
            state="readonly",
        )
        self.level_combo.pack(side="left", padx=(8, 12))

        self.clear_btn = ctk.CTkButton(
            toolbar,
            text="清除日志",
            width=100,
            height=28,
            font=("Microsoft YaHei", 11),
            fg_color="transparent",
            hover_color="#3D3D5C",
            text_color="#AAAAAA",
            command=self.clear,
        )
        self.clear_btn.pack(side="left")

        # 自动滚动开关
        self.auto_scroll_var = ctk.BooleanVar(value=True)
        self.auto_scroll_switch = ctk.CTkSwitch(
            toolbar,
            text="自动滚动",
            variable=self.auto_scroll_var,
            font=("Microsoft YaHei", 11),
            switch_width=40,
            switch_height=20,
            fg_color="#3D3D5C",
            progress_color="#FF6B35",
            button_color="#FFFFFF",
            text_color="#AAAAAA",
        )
        self.auto_scroll_switch.pack(side="right")

        # 日志文本框
        self.text = ctk.CTkTextbox(
            self,
            font=("Microsoft YaHei", 11),
            fg_color="#16162A",
            text_color="#E0E0E0",
            corner_radius=8,
            border_width=1,
            border_color="#2D2D44",
            wrap="word",
            activate_scrollbars=True,
            scrollbar_button_color="#3D3D5C",
            scrollbar_button_hover_color="#555577",
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def log(self, level, message):
        """追加日志"""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        try:
            if levels.index(level) < levels.index(self.level_var.get()):
                return
        except ValueError:
            pass

        color = self.LEVEL_COLORS.get(level, "#E0E0E0")
        timestamp = self._get_timestamp()

        self.text.configure(state="normal")
        self.text.insert("end", f"{timestamp} ", "timestamp")
        self.text.insert("end", f"[{level}] ", level)
        self.text.insert("end", f"{message}\n", "message")

        self.text.tag_config("timestamp", foreground="#666688")
        self.text.tag_config(level, foreground=color)
        self.text.tag_config("message", foreground="#E0E0E0")

        if self.auto_scroll_var.get():
            self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    @staticmethod
    def _get_timestamp():
        import time
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
