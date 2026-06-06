"""
代理控制标签页（customtkinter 现代化版本）
- 状态卡片
- 启动/停止控制
- 实时日志输出
- 统计卡片
"""
import customtkinter as ctk

from gui.log_widget import LogWidget


class ProxyTab:
    def __init__(self, master, on_toggle=None, on_change=None):
        self.master = master
        self.on_toggle = on_toggle
        self.on_change = on_change
        self._init_ui()

    def _init_ui(self):
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(2, weight=1)

        # ===== 顶部状态卡片 =====
        status_card = ctk.CTkFrame(self.master, fg_color="#FFFFFF", corner_radius=16)
        status_card.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 12))
        status_card.grid_columnconfigure(1, weight=1)

        # 左侧状态
        left = ctk.CTkFrame(status_card, fg_color="transparent")
        left.pack(side="left", padx=16, pady=14)

        self.status_dot = ctk.CTkLabel(
            left,
            text="●",
            font=("Microsoft YaHei", 16),
            text_color="#FF4444",
        )
        self.status_dot.pack(side="left")

        self.status_text = ctk.CTkLabel(
            left,
            text="已停止",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#FF4444",
        )
        self.status_text.pack(side="left", padx=(6, 4))

        self.listen_label = ctk.CTkLabel(
            left,
            text="本机监听",
            font=("Microsoft YaHei", 12),
            text_color="#888888",
        )
        self.listen_label.pack(side="left")

        # 右侧控制
        right = ctk.CTkFrame(status_card, fg_color="transparent")
        right.pack(side="right", padx=16, pady=14)

        ctk.CTkLabel(
            right,
            text="转发端口",
            font=("Microsoft YaHei", 12),
            text_color="#666666",
        ).pack(side="left", padx=(0, 8))

        self.port_var = ctk.StringVar(value="8317")
        self.port_entry = ctk.CTkEntry(
            right,
            textvariable=self.port_var,
            width=80,
            height=32,
            font=("Microsoft YaHei", 12),
            corner_radius=8,
            fg_color="#F5F5F7",
            border_color="#E0E0E0",
            text_color="#333333",
        )
        self.port_entry.pack(side="left", padx=(0, 12))

        self.start_btn = ctk.CTkButton(
            right,
            text="▶ 启动代理",
            width=110,
            height=34,
            font=("Microsoft YaHei", 12, "bold"),
            fg_color="#FF6B35",
            hover_color="#E55A2B",
            text_color="#FFFFFF",
            corner_radius=10,
            command=self._toggle,
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            right,
            text="⏹ 停止代理",
            width=110,
            height=34,
            font=("Microsoft YaHei", 12, "bold"),
            fg_color="#FF4444",
            hover_color="#DD3333",
            text_color="#FFFFFF",
            corner_radius=10,
            command=self._toggle,
        )
        self.stop_btn.pack(side="left")
        self.stop_btn.pack_forget()  # 默认隐藏

        # ===== 使用提示 =====
        tip_card = ctk.CTkFrame(self.master, fg_color="#FFF8F5", corner_radius=12, border_width=1, border_color="#FFE0D0")
        tip_card.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 12))

        tip_inner = ctk.CTkFrame(tip_card, fg_color="transparent")
        tip_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            tip_inner,
            text="使用提示",
            font=("Microsoft YaHei", 12, "bold"),
            text_color="#FF6B35",
        ).pack(anchor="w", pady=(0, 6))

        tips = (
            "1. 在 Provider 标签页配置好 Kimi Code 的 API Key 和 Base URL\n"
            "2. 点击「启动代理」后，代理会监听上方配置的地址\n"
            "3. 在 Codex 或 Claude Code 中设置环境变量:\n"
            "   ANTHROPIC_BASE_URL=http://127.0.0.1:8317/v1\n"
            "   ANTHROPIC_AUTH_TOKEN=任意值（代理会自动替换为真实 Key）"
        )
        ctk.CTkLabel(
            tip_inner,
            text=tips,
            font=("Microsoft YaHei", 11),
            text_color="#666666",
            justify="left",
        ).pack(anchor="w")

        # ===== 日志区域 =====
        self.log_widget = LogWidget(self.master)
        self.log_widget.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 12))

        # ===== 底部统计卡片 =====
        stats_frame = ctk.CTkFrame(self.master, fg_color="transparent")
        stats_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 4))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_cards = []
        stat_configs = [
            ("总请求", "●", "#4FC3F7", "0"),
            ("成功", "●", "#81C784", "0"),
            ("失败", "●", "#EF5350", "0"),
            ("今日", "●", "#FFB74D", "0"),
        ]

        for i, (title, icon, color, value) in enumerate(stat_configs):
            card = self._build_stat_card(stats_frame, title, icon, color, value)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            self.stat_cards.append((card, title, value))

    def _build_stat_card(self, parent, title, icon, color, value):
        card = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#E8E8E8")
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top,
            text=icon,
            font=("Microsoft YaHei", 18),
            text_color=color,
        ).pack(side="left")

        ctk.CTkLabel(
            top,
            text=title,
            font=("Microsoft YaHei", 12),
            text_color="#888888",
        ).pack(side="left", padx=(8, 0))

        value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=("Microsoft YaHei", 24, "bold"),
            text_color="#1A1A1A",
        )
        value_label.pack(anchor="w", pady=(4, 0))

        return card

    def load_config(self, host, port):
        self.host = host
        self.port_var.set(str(port))

    def get_host(self):
        return getattr(self, 'host', '127.0.0.1')

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
            self.status_dot.configure(text_color="#28C76F")
            self.status_text.configure(text="运行中", text_color="#28C76F")
            self.start_btn.pack_forget()
            self.stop_btn.pack(side="left", padx=(0, 8))
            self.port_entry.configure(state="disabled")
        else:
            self.status_dot.configure(text_color="#FF4444")
            self.status_text.configure(text="已停止", text_color="#FF4444")
            self.stop_btn.pack_forget()
            self.start_btn.pack(side="left", padx=(0, 8))
            self.port_entry.configure(state="normal")

    def log(self, level, message):
        self.log_widget.log(level, message)
