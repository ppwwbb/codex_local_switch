"""
Provider 配置标签页（tkinter 版本）
- 左侧 Provider 列表（带添加/删除）
- 右侧选中 Provider 的详细配置表单
"""
import tkinter as tk
from tkinter import ttk, messagebox

from config import Provider


class ProviderTab(tk.Frame):
    def __init__(self, master=None, on_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_change = on_change
        self.providers = []
        self.current_provider_id = None
        self._init_ui()

    def _init_ui(self):
        # 左右分栏
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 左侧 Provider 列表
        left = tk.Frame(self.paned, width=200)
        tk.Label(left, text="Providers", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))

        self.listbox = tk.Listbox(left, selectmode=tk.SINGLE)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = tk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(4, 0))
        tk.Button(btn_frame, text="+ 添加", command=self._add).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(btn_frame, text="- 删除", command=self._delete).pack(side=tk.LEFT)

        self.paned.add(left)

        # 右侧配置表单
        right = tk.Frame(self.paned, padx=12)
        tk.Label(right, text="Provider 配置", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))

        form = tk.Frame(right)
        form.pack(fill=tk.X)

        tk.Label(form, text="名称:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=tk.EW, padx=(8, 0))

        tk.Label(form, text="Base URL:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.url_var = tk.StringVar()
        tk.Entry(form, textvariable=self.url_var, width=40).grid(row=1, column=1, sticky=tk.EW, padx=(8, 0))

        tk.Label(form, text="API Key:").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.key_var = tk.StringVar()
        self.key_entry = tk.Entry(form, textvariable=self.key_var, width=40, show="*")
        self.key_entry.grid(row=2, column=1, sticky=tk.EW, padx=(8, 0))

        tk.Label(form, text="默认模型:").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.model_var = tk.StringVar()
        tk.Entry(form, textvariable=self.model_var, width=40).grid(row=3, column=1, sticky=tk.EW, padx=(8, 0))

        self.show_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(form, text="显示 Key", variable=self.show_key_var, command=self._toggle_key).grid(row=4, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        form.columnconfigure(1, weight=1)

        save_btn = tk.Button(right, text="保存当前配置", bg="#0066cc", fg="white", command=self._save)
        save_btn.pack(anchor=tk.W, pady=(12, 0))

        self.paned.add(right)

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
        self.listbox.delete(0, tk.END)
        for p in self.providers:
            self.listbox.insert(tk.END, p.name or p.id)

    def _select_by_id(self, provider_id):
        for i, p in enumerate(self.providers):
            if p.id == provider_id:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(i)
                self.listbox.see(i)
                self._load_form(p)
                return

    def _on_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if 0 <= idx < len(self.providers):
            p = self.providers[idx]
            self.current_provider_id = p.id
            self._load_form(p)

    def _load_form(self, p):
        self.name_var.set(p.name)
        self.url_var.set(p.base_url)
        self.key_var.set(p.api_key)
        self.model_var.set(p.model)

    def _toggle_key(self):
        if self.show_key_var.get():
            self.key_entry.config(show="")
        else:
            self.key_entry.config(show="*")

    def _add(self):
        import uuid
        new_id = "provider_" + uuid.uuid4().hex[:6]
        p = Provider(id=new_id, name="新 Provider")
        self.providers.append(p)
        self.current_provider_id = new_id
        self._refresh_list()
        self._select_by_id(new_id)
        if self.on_change:
            self.on_change()

    def _delete(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        p = self.providers[idx]
        if messagebox.askyesno("确认删除", f'确定要删除 Provider "{p.name}" 吗？'):
            self.providers.pop(idx)
            if self.current_provider_id == p.id:
                self.current_provider_id = self.providers[0].id if self.providers else None
            self._refresh_list()
            self._select_by_id(self.current_provider_id)
            if self.on_change:
                self.on_change()

    def _save(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个 Provider")
            return
        idx = selection[0]
        p = self.providers[idx]
        p.name = self.name_var.get().strip() or p.name
        p.base_url = self.url_var.get().strip()
        p.api_key = self.key_var.get().strip()
        p.model = self.model_var.get().strip()
        self._refresh_list()
        self._select_by_id(p.id)
        if self.on_change:
            self.on_change()
        messagebox.showinfo("保存成功", "Provider 配置已更新")
