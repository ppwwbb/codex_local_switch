"""
Provider 配置标签页（customtkinter 现代化版本）
- 卡片式 Provider 列表
- 右侧配置面板
"""
import uuid
import customtkinter as ctk
from tkinter import messagebox

from config import Provider


class ProviderTab:
    def __init__(self, master, on_change=None):
        self.master = master
        self.on_change = on_change
        self.providers = []
        self.current_provider_id = None
        self._init_ui()

    def _init_ui(self):
        # 主布局：左右分栏
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_columnconfigure(1, weight=2)
        self.master.grid_rowconfigure(0, weight=1)

        # 左侧：Provider 列表
        left_frame = ctk.CTkFrame(self.master, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # 左侧标题 + 添加按钮
        left_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        left_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_header,
            text="Providers",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#1A1A1A",
        ).grid(row=0, column=0, sticky="w")

        self.add_btn = ctk.CTkButton(
            left_header,
            text="+ 添加",
            width=80,
            height=32,
            font=("Microsoft YaHei", 12),
            fg_color="#FF6B35",
            hover_color="#E55A2B",
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._add,
        )
        self.add_btn.grid(row=0, column=1, sticky="e")

        # Provider 列表容器（可滚动）
        self.list_container = ctk.CTkScrollableFrame(
            left_frame,
            fg_color="transparent",
            scrollbar_button_color="#CCCCCC",
            scrollbar_button_hover_color="#AAAAAA",
        )
        self.list_container.grid(row=1, column=0, sticky="nsew")
        self.list_container.grid_columnconfigure(0, weight=1)

        # 右侧：配置表单
        right_frame = ctk.CTkFrame(self.master, fg_color="#FFFFFF", corner_radius=16)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # 标题
        ctk.CTkLabel(
            right_frame,
            text="Provider 配置",
            font=("Microsoft YaHei", 16, "bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            right_frame,
            text="编辑选中 Provider 的详细信息",
            font=("Microsoft YaHei", 11),
            text_color="#888888",
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # 表单
        form_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=20, pady=8)
        form_frame.grid_columnconfigure(1, weight=1)

        # 名称
        ctk.CTkLabel(form_frame, text="名称", font=("Microsoft YaHei", 12), text_color="#333333").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(form_frame, textvariable=self.name_var, font=("Microsoft YaHei", 12), height=36, corner_radius=8)
        self.name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # Base URL
        ctk.CTkLabel(form_frame, text="Base URL", font=("Microsoft YaHei", 12), text_color="#333333").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(form_frame, textvariable=self.url_var, font=("Microsoft YaHei", 12), height=36, corner_radius=8)
        self.url_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # API Key
        ctk.CTkLabel(form_frame, text="API Key", font=("Microsoft YaHei", 12), text_color="#333333").grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.key_var = ctk.StringVar()
        self.key_entry = ctk.CTkEntry(form_frame, textvariable=self.key_var, font=("Microsoft YaHei", 12), height=36, corner_radius=8, show="*")
        self.key_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # 默认模型
        ctk.CTkLabel(form_frame, text="默认模型", font=("Microsoft YaHei", 12), text_color="#333333").grid(row=6, column=0, sticky="w", pady=(0, 4))
        self.model_var = ctk.StringVar()
        self.model_entry = ctk.CTkEntry(form_frame, textvariable=self.model_var, font=("Microsoft YaHei", 12), height=36, corner_radius=8)
        self.model_entry.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # 显示 Key 开关
        self.show_key_var = ctk.BooleanVar(value=False)
        self.show_key_switch = ctk.CTkSwitch(
            form_frame,
            text="显示 Key",
            variable=self.show_key_var,
            command=self._toggle_key,
            font=("Microsoft YaHei", 11),
            switch_width=40,
            switch_height=20,
            fg_color="#CCCCCC",
            progress_color="#FF6B35",
            button_color="#FFFFFF",
        )
        self.show_key_switch.grid(row=8, column=0, sticky="w", pady=(0, 16))

        # 保存按钮
        self.save_btn = ctk.CTkButton(
            right_frame,
            text="保存当前配置",
            font=("Microsoft YaHei", 13, "bold"),
            height=40,
            fg_color="#FF6B35",
            hover_color="#E55A2B",
            text_color="#FFFFFF",
            corner_radius=10,
            command=self._save,
        )
        self.save_btn.pack(anchor="w", padx=20, pady=(8, 8))

        # 删除按钮
        self.delete_btn = ctk.CTkButton(
            right_frame,
            text="删除当前 Provider",
            font=("Microsoft YaHei", 12),
            height=36,
            fg_color="#FF4444",
            hover_color="#DD3333",
            text_color="#FFFFFF",
            corner_radius=10,
            command=self._delete,
        )
        self.delete_btn.pack(anchor="w", padx=20, pady=(0, 16))

    def load_providers(self, providers, current_id):
        self.providers = list(providers)
        self.current_provider_id = current_id
        self._refresh_list()
        self._select_by_id(current_id)

    def get_providers(self):
        return self.providers

    def get_current_provider_id(self):
        return self.current_provider_id

    def _refresh_list(self):
        # 清空列表
        for widget in self.list_container.winfo_children():
            widget.destroy()

        for i, p in enumerate(self.providers):
            card = self._build_provider_card(p, i)
            card.pack(fill="x", pady=(0, 8), padx=2)

    def _build_provider_card(self, p, index):
        is_selected = p.id == self.current_provider_id
        is_active = getattr(p, 'enabled', True)

        # 卡片容器
        card = ctk.CTkFrame(
            self.list_container,
            fg_color="#FFFAF7" if is_selected else "#FFFFFF",
            corner_radius=12,
            border_width=2 if is_selected else 1,
            border_color="#FF6B35" if is_selected else "#E8E8E8",
        )
        card.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        # 卡片内容
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        inner.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        # 左侧：图标/名称
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")
        left.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        # 首字母图标
        icon_text = (p.name[0] if p.name else "?").upper()
        icon = ctk.CTkLabel(
            left,
            text=icon_text,
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#FFFFFF",
            fg_color="#FF6B35",
            width=36,
            height=36,
            corner_radius=10,
        )
        icon.pack(side="left")
        icon.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        # 名称和 URL
        info = ctk.CTkFrame(left, fg_color="transparent")
        info.pack(side="left", padx=(10, 0))
        info.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        name_label = ctk.CTkLabel(
            info,
            text=p.name or "未命名",
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#1A1A1A",
        )
        name_label.pack(anchor="w")
        name_label.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        url_label = ctk.CTkLabel(
            info,
            text=p.base_url or "",
            font=("Microsoft YaHei", 10),
            text_color="#888888",
        )
        url_label.pack(anchor="w")
        url_label.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        # 右侧：状态/操作
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        right.bind("<Button-1>", lambda e, pid=p.id: self._select_card(pid))

        if is_active:
            status = ctk.CTkLabel(
                right,
                text="● 启用",
                font=("Microsoft YaHei", 10, "bold"),
                text_color="#28C76F",
            )
            status.pack(side="right", padx=(8, 0))
        else:
            status = ctk.CTkLabel(
                right,
                text="● 停用",
                font=("Microsoft YaHei", 10, "bold"),
                text_color="#FF4444",
            )
            status.pack(side="right", padx=(8, 0))

        return card

    def _select_card(self, provider_id):
        self.current_provider_id = provider_id
        self._refresh_list()
        self._load_form(next((x for x in self.providers if x.id == provider_id), None))

    def _select_by_id(self, provider_id):
        for p in self.providers:
            if p.id == provider_id:
                self._load_form(p)
                return

    def _load_form(self, p):
        if p is None:
            self.name_var.set("")
            self.url_var.set("")
            self.key_var.set("")
            self.model_var.set("")
            return
        self.name_var.set(p.name)
        self.url_var.set(p.base_url)
        self.key_var.set(p.api_key)
        self.model_var.set(p.model)

    def _toggle_key(self):
        if self.show_key_var.get():
            self.key_entry.configure(show="")
        else:
            self.key_entry.configure(show="*")

    def _add(self):
        new_id = "provider_" + uuid.uuid4().hex[:6]
        p = Provider(id=new_id, name="新 Provider")
        self.providers.append(p)
        self.current_provider_id = new_id
        self._refresh_list()
        self._load_form(p)
        if self.on_change:
            self.on_change()

    def _delete(self):
        if self.current_provider_id is None:
            messagebox.showwarning("提示", "请先选择一个 Provider")
            return
        p = next((x for x in self.providers if x.id == self.current_provider_id), None)
        if p is None:
            return
        if messagebox.askyesno("确认删除", f'确定要删除 Provider "{p.name}" 吗？'):
            self.providers = [x for x in self.providers if x.id != p.id]
            self.current_provider_id = self.providers[0].id if self.providers else None
            self._refresh_list()
            self._select_by_id(self.current_provider_id)
            if self.on_change:
                self.on_change()

    def _save(self):
        if self.current_provider_id is None:
            messagebox.showwarning("提示", "请先选择一个 Provider")
            return
        p = next((x for x in self.providers if x.id == self.current_provider_id), None)
        if p is None:
            messagebox.showwarning("提示", "请先选择一个 Provider")
            return
        p.name = self.name_var.get().strip() or p.name
        p.base_url = self.url_var.get().strip()
        p.api_key = self.key_var.get().strip()
        p.model = self.model_var.get().strip()
        self._refresh_list()
        if self.on_change:
            self.on_change()
        messagebox.showinfo("保存成功", "Provider 配置已更新")
