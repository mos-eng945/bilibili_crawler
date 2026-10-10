"""任务完成提示弹窗。"""

from pathlib import Path

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from config import OUTPUT_DIR
from qt_ui.dialogs.browser import DataBrowserDialog
from qt_ui.theme import (
    APP_STYLE,
)


def relative_display(path):
    """把绝对路径显示成 `output/...` 形式。"""
    try:
        return "output/" + Path(path).relative_to(OUTPUT_DIR).as_posix()
    except ValueError:
        return str(path)


class CompletionDialog(QDialog):
    """任务完成后的统一提示框。"""

    def __init__(self, task_name, path=None, parent=None):
        super().__init__(parent)
        self.path = Path(path) if path else None
        self.setObjectName("CompletionDialog")
        self.setWindowTitle("任务完成")
        self.setModal(True)
        self.setFixedWidth(440)
        self.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(14)

        badge = QLabel("✓")
        badge.setObjectName("CompletionBadge")
        badge.setFixedSize(46, 46)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        heading = QVBoxLayout()
        heading.setSpacing(3)

        title = QLabel("任务已完成")
        title.setObjectName("CompletionTitle")
        heading.addWidget(title)

        message = QLabel(f"{task_name}已完成。")
        message.setObjectName("CompletionMessage")
        message.setWordWrap(True)
        heading.addWidget(message)
        header.addLayout(heading, 1)
        layout.addLayout(header)

        panel = QFrame()
        panel.setObjectName("CompletionPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(5)

        panel_label = QLabel("保存位置" if path else "任务状态")
        panel_label.setObjectName("CompletionPanelLabel")
        panel_layout.addWidget(panel_label)

        display_path = "任务已成功结束"

        if path:
            display_path = relative_display(path)

        panel_value = QLabel(display_path)
        panel_value.setObjectName("CompletionPath")
        panel_value.setWordWrap(True)
        panel_value.setToolTip(str(path) if path else "")
        panel_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        panel_layout.addWidget(panel_value)
        layout.addWidget(panel)

        actions = QHBoxLayout()
        actions.addStretch(1)

        if path:
            open_button = QPushButton("查看数据")
            open_button.setMinimumWidth(88)
            open_button.setToolTip("在数据查看里打开这次产出的目录")
            open_button.clicked.connect(self._open_data_view)
            actions.addWidget(open_button)

        close_button = QPushButton("完成")
        close_button.setObjectName("PrimaryButton")
        close_button.setMinimumWidth(96)
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _open_data_view(self):
        """先关掉完成提示，再在程序里打开数据查看。"""
        parent = self.parent()
        self.accept()

        if self.path is None or parent is None:
            return

        DataBrowserDialog(parent, initial_path=self.path).exec()


