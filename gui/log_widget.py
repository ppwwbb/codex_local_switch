"""
日志输出组件，带级别过滤和自动滚动
"""
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QComboBox, QLabel


class LogEmitter(QObject):
    new_log = pyqtSignal(str, str)  # level, message


class LogWidget(QWidget):
    """带过滤和清除功能的日志面板"""

    LEVEL_COLORS = {
        "DEBUG": "#808080",
        "INFO": "#0066cc",
        "WARNING": "#ff9900",
        "ERROR": "#cc0000",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.emitter = LogEmitter()
        self.emitter.new_log.connect(self._append_log)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("日志级别:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        toolbar.addWidget(self.level_combo)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 日志文本框
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.text_edit)

    def log(self, level: str, message: str) -> None:
        """线程安全的日志写入（通过信号）"""
        self.emitter.new_log.emit(level, message)

    def _append_log(self, level: str, message: str) -> None:
        """实际追加日志到界面"""
        # 级别过滤
        current_level = self.level_combo.currentText()
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if levels.index(level) < levels.index(current_level):
            return

        color = self.LEVEL_COLORS.get(level, "#000000")
        html = f'<span style="color:{color}">[{level}]</span> {message}<br>'
        self.text_edit.insertHtml(html)
        # 自动滚动到底部
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self.text_edit.clear()
