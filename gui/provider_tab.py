"""
Provider 配置标签页
参考 CC Switch 的 Provider 管理界面：
- 左侧 Provider 列表（带添加/删除）
- 右侧选中 Provider 的详细配置表单
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPushButton, QFormLayout, QMessageBox, QSplitter
)

from config import Provider


class ProviderTab(QWidget):
    config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.providers = []
        self.current_provider_id = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 左侧 Provider 列表
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Providers"))

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        left_panel.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加")
        self.add_btn.clicked.connect(self._add_provider)
        self.del_btn = QPushButton("- 删除")
        self.del_btn.clicked.connect(self._delete_provider)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        left_panel.addLayout(btn_layout)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(240)

        # 右侧配置表单
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Provider 配置"))

        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("显示名称，如 Kimi Code")
        form.addRow("名称:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://api.kimi.com/coding/v1")
        form.addRow("Base URL:", self.url_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("sk-xxxxxxxx")
        self.key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.key_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("kimi-k2-0711-preview")
        form.addRow("默认模型:", self.model_edit)

        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        form.addRow("", self.show_key_btn)

        form_widget = QWidget()
        form_widget.setLayout(form)
        right_panel.addWidget(form_widget)

        self.save_btn = QPushButton("保存当前配置")
        self.save_btn.setStyleSheet("QPushButton { background-color: #0066cc; color: white; padding: 8px; }")
        self.save_btn.clicked.connect(self._save_current)
        right_panel.addWidget(self.save_btn)
        right_panel.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

    def load_providers(self, providers, current_id):
        """从外部加载 provider 列表"""
        self.providers = list(providers)
        self.current_provider_id = current_id
        self._refresh_list()
        self._select_provider(current_id)

    def get_providers(self):
        """返回当前所有 provider"""
        return self.providers

    def get_current_provider_id(self):
        return self.current_provider_id

    def _refresh_list(self):
        self.list_widget.clear()
        for p in self.providers:
            item = QListWidgetItem(p.name or p.id)
            item.setData(256, p.id)  # Qt.UserRole = 256
            self.list_widget.addItem(item)

    def _select_provider(self, provider_id):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(256) == provider_id:
                self.list_widget.setCurrentRow(i)
                return

    def _on_selection_changed(self, row):
        if row < 0 or row >= len(self.providers):
            self._clear_form()
            return
        provider = self.providers[row]
        self.current_provider_id = provider.id
        self.name_edit.setText(provider.name)
        self.url_edit.setText(provider.base_url)
        self.key_edit.setText(provider.api_key)
        self.model_edit.setText(provider.model)

    def _clear_form(self):
        self.name_edit.clear()
        self.url_edit.clear()
        self.key_edit.clear()
        self.model_edit.clear()

    def _toggle_key_visibility(self, checked):
        self.key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.show_key_btn.setText("隐藏" if checked else "显示")

    def _add_provider(self):
        import uuid as _uuid
        new_id = "provider_" + _uuid.uuid4().hex[:6]
        new_provider = Provider(id=new_id, name="新 Provider")
        self.providers.append(new_provider)
        self.current_provider_id = new_id
        self._refresh_list()
        self._select_provider(new_id)
        self.config_changed.emit()

    def _delete_provider(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.providers):
            return
        provider = self.providers[row]
        reply = QMessageBox.question(
            self, "确认删除",
            f'确定要删除 Provider "{provider.name}" 吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.providers.pop(row)
            if self.current_provider_id == provider.id:
                self.current_provider_id = self.providers[0].id if self.providers else None
            self._refresh_list()
            self._select_provider(self.current_provider_id)
            self.config_changed.emit()

    def _save_current(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.providers):
            QMessageBox.warning(self, "提示", "请先选择一个 Provider")
            return
        provider = self.providers[row]
        provider.name = self.name_edit.text().strip() or provider.name
        provider.base_url = self.url_edit.text().strip()
        provider.api_key = self.key_edit.text().strip()
        provider.model = self.model_edit.text().strip()
        self._refresh_list()
        self._select_provider(provider.id)
        self.config_changed.emit()
        QMessageBox.information(self, "保存成功", "Provider 配置已更新")
