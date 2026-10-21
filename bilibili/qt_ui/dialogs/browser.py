"""output 目录数据浏览弹窗。"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import OUTPUT_DIR
from qt_ui.dialogs.constants import BROWSABLE_SUFFIXES
from qt_ui.dialogs.models import SortableTableWidgetItem
from qt_ui.dialogs.preview import DataPreviewDialog
from qt_ui.formatting import (
    friendly_file_name,
    friendly_video_name,
)
from qt_ui.theme import (
    APP_STYLE,
    icon,
)


def is_subtitle_json(path):
    """字幕 JSON 只是中间产物，浏览和统计时只保留 SRT。"""
    name = Path(path).name.lower()
    return name.startswith("subtitle_") and name.endswith(".json")


class DataBrowserDialog(QDialog):
    """按 output 目录层级浏览数据。"""

    def __init__(self, parent=None, initial_path=None):
        super().__init__(parent)
        self.output_dir = OUTPUT_DIR
        self.root_dir = self.output_dir
        self.current_dir = self.root_dir
        self.browser_entries = []
        self.browser_sort_column = 2
        self.browser_sort_order = Qt.SortOrder.DescendingOrder

        self.setWindowTitle("数据查看")
        self.resize(920, 620)
        self.setMinimumSize(620, 400)
        self.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.path_label = QLabel()
        self.path_label.setObjectName("PreviewMeta")
        layout.addWidget(self.path_label)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.browser_page = QWidget()
        browser_layout = QVBoxLayout(self.browser_page)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(8)

        self.browser_table = QTableWidget(0, 3)
        self.browser_table.setHorizontalHeaderLabels(
            ["名称", "目录概况", "更新时间"]
        )
        self.browser_table.verticalHeader().setVisible(False)
        self.browser_table.verticalHeader().setDefaultSectionSize(32)
        self.browser_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.browser_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.browser_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.browser_table.setShowGrid(False)
        self.browser_table.setAlternatingRowColors(True)
        self.browser_table.horizontalHeader().setSectionsClickable(True)
        self.browser_table.horizontalHeader().setSortIndicatorShown(True)
        self.browser_table.horizontalHeader().setSortIndicator(
            2,
            Qt.SortOrder.DescendingOrder,
        )
        self.browser_table.horizontalHeader().sectionClicked.connect(
            self._sort_browser
        )
        browser_header = self.browser_table.horizontalHeader()
        browser_header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        browser_header.setStretchLastSection(False)
        self.browser_table.setColumnWidth(0, 380)
        self.browser_table.setColumnWidth(1, 260)
        self.browser_table.setColumnWidth(2, 150)
        self.browser_table.cellDoubleClicked.connect(
            lambda row, column: self._activate_row(row)
        )
        browser_layout.addWidget(self.browser_table, 1)
        self.stack.addWidget(self.browser_page)

        self.tree_page = QWidget()
        tree_layout = QVBoxLayout(self.tree_page)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        self.directory_tree = QTreeWidget()
        self.directory_tree.setHeaderLabels(["全部目录", "数据文件"])
        self.directory_tree.setAlternatingRowColors(True)
        self.directory_tree.itemDoubleClicked.connect(
            self._open_tree_directory
        )
        tree_layout.addWidget(self.directory_tree)
        self.stack.addWidget(self.tree_page)

        actions = QHBoxLayout()
        self.parent_button = QPushButton("返回")
        self.parent_button.setIcon(icon("icon-up.svg"))
        self.parent_button.clicked.connect(self._go_parent)
        actions.addWidget(self.parent_button)

        self.toggle_tree_button = QPushButton("全部目录")
        self.toggle_tree_button.clicked.connect(self._toggle_tree)
        actions.addWidget(self.toggle_tree_button)
        actions.addStretch(1)

        self.view_button = QPushButton("打开")
        self.view_button.setObjectName("PrimaryButton")
        self.view_button.clicked.connect(self._view_selected)
        actions.addWidget(self.view_button)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        start_path = self.root_dir

        if initial_path is not None:
            candidate = Path(initial_path).resolve()

            if candidate.is_file():
                candidate = candidate.parent

            if (
                candidate == self.root_dir
                or self.root_dir in candidate.parents
            ):
                start_path = candidate

        self._navigate_to(start_path, auto_open_single=False)

    def _navigate_to(self, path, auto_open_single=True):
        self.current_dir = Path(path).resolve()

        if auto_open_single and self.current_dir != self.root_dir:
            data_file = self._single_data_file(self.current_dir)

            if data_file:
                DataPreviewDialog(
                    data_file,
                    self,
                    display_name=friendly_file_name(data_file),
                ).exec()
                return

        self.stack.setCurrentWidget(self.browser_page)
        self.toggle_tree_button.setText("全部目录")
        self._populate_browser()

    @staticmethod
    def _single_data_file(directory):
        data_files = []
        child_directories = []

        for path in directory.iterdir():
            if path.name in {".git", "__pycache__"}:
                continue

            if path.is_dir():
                child_directories.append(path)
            elif (
                path.suffix.lower() in BROWSABLE_SUFFIXES
                and not is_subtitle_json(path)
            ):
                data_files.append(path)

        if len(data_files) == 1 and not child_directories:
            return data_files[0]

        return None

    def _populate_browser(self):
        if self.current_dir.exists():
            paths = sorted(
                (
                    path
                    for path in self.current_dir.iterdir()
                    if path.name not in {".git", "__pycache__"}
                    and not is_subtitle_json(path)
                ),
                key=self._browser_sort_key,
            )
        else:
            paths = []

        self.browser_entries = paths
        self.browser_table.setRowCount(len(paths))
        relative_path = self.current_dir.relative_to(self.root_dir)
        display_path = (
            "output"
            if not relative_path.parts
            else f"output/{relative_path.as_posix()}"
        )
        self.path_label.setText(display_path)
        self.parent_button.setEnabled(self.current_dir != self.root_dir)

        for row, path in enumerate(paths):
            if path.is_dir():
                name = friendly_video_name(path.name)
                summary = self._directory_summary(path)
            else:
                name = friendly_file_name(path)
                summary = self._file_summary(path)

            try:
                modified_at = path.stat().st_mtime
                time_text = self._friendly_time(modified_at)
            except OSError:
                modified_at = float("-inf")
                time_text = ""

            name_item = SortableTableWidgetItem(
                name,
                (name.casefold(), name),
            )
            name_item.setData(
                Qt.ItemDataRole.UserRole,
                str(path),
            )
            summary_item = SortableTableWidgetItem(
                summary,
                (summary.casefold(), summary),
            )
            time_item = SortableTableWidgetItem(
                time_text,
                modified_at,
            )
            self.browser_table.setItem(row, 0, name_item)
            self.browser_table.setItem(row, 1, summary_item)
            self.browser_table.setItem(row, 2, time_item)
            name_item.setToolTip(f"{name}\n{path}")
            self.browser_table.item(row, 1).setToolTip(summary)
            self.browser_table.item(row, 2).setToolTip(
                f"{time_text}\n{path}"
            )

        self._apply_browser_sort()

    def _sort_browser(self, column):
        order = Qt.SortOrder.AscendingOrder

        if (
            self.browser_sort_column == column
            and self.browser_sort_order == Qt.SortOrder.AscendingOrder
        ):
            order = Qt.SortOrder.DescendingOrder

        self.browser_sort_column = column
        self.browser_sort_order = order
        self._apply_browser_sort()

    def _apply_browser_sort(self):
        self.browser_table.sortItems(
            self.browser_sort_column,
            self.browser_sort_order,
        )
        header = self.browser_table.horizontalHeader()
        header.setSortIndicator(
            self.browser_sort_column,
            self.browser_sort_order,
        )
        header.setSortIndicatorShown(True)

    @staticmethod
    def _browser_sort_key(path):
        if path.is_dir():
            return (0, path.name.lower())

        if path.name.lower() == "video_info.json":
            return (1, path.name.lower())

        return (2, path.name.lower())

    def _activate_row(self, row):
        if row < 0 or row >= self.browser_table.rowCount():
            return

        item = self.browser_table.item(row, 0)
        path_text = item.data(Qt.ItemDataRole.UserRole) if item else None

        if not path_text:
            return

        path = Path(path_text)

        if path.is_dir():
            self._navigate_to(path)
            return

        if path.suffix.lower() in BROWSABLE_SUFFIXES:
            DataPreviewDialog(
                path,
                self,
                display_name=friendly_file_name(path),
            ).exec()
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _view_selected(self):
        self._activate_row(self.browser_table.currentRow())

    def _go_parent(self):
        if self.current_dir == self.root_dir:
            return

        self._navigate_to(self.current_dir.parent)

    def _toggle_tree(self):
        if self.stack.currentWidget() is self.tree_page:
            self.stack.setCurrentWidget(self.browser_page)
            self.toggle_tree_button.setText("全部目录")
            return

        self._populate_directory_tree()
        self.stack.setCurrentWidget(self.tree_page)
        self.toggle_tree_button.setText("返回目录")

    def _populate_directory_tree(self):
        self.directory_tree.clear()

        if not self.output_dir.exists():
            return

        root_item = QTreeWidgetItem(["output", "0"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self.output_dir))
        self.directory_tree.addTopLevelItem(root_item)
        root_count = self._add_tree_children(root_item, self.output_dir)
        root_item.setText(1, str(root_count))
        root_item.setExpanded(True)

    def _add_tree_children(self, parent_item, directory):
        total_files = 0

        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if (
                path.is_file()
                and path.suffix.lower() in BROWSABLE_SUFFIXES
                and not is_subtitle_json(path)
            ):
                total_files += 1
                continue

            if not path.is_dir() or path.name == "__pycache__":
                continue

            item = QTreeWidgetItem([path.name, "0"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            parent_item.addChild(item)
            child_files = self._add_tree_children(item, path)
            item.setText(1, str(child_files))
            total_files += child_files

        return total_files

    def _open_tree_directory(self, item):
        path_text = item.data(0, Qt.ItemDataRole.UserRole)

        if path_text:
            self._navigate_to(Path(path_text))

    def _directory_summary(self, path):
        child_dirs = 0
        direct_files = 0

        try:
            for child in path.iterdir():
                if child.is_dir():
                    child_dirs += 1
                elif (
                    child.suffix.lower() in BROWSABLE_SUFFIXES
                    and not is_subtitle_json(child)
                ):
                    direct_files += 1
        except OSError:
            return "无法读取"

        if child_dirs:
            return f"{child_dirs} 个子目录 · {direct_files} 个数据文件"

        return f"{direct_files} 个数据文件"

    def _file_summary(self, path):
        try:
            size = path.stat().st_size
        except OSError:
            size = 0

        if size >= 1024 * 1024:
            size_text = f"{size / (1024 * 1024):.1f} MB"
        else:
            size_text = f"{size / 1024:.1f} KB"

        return f"{path.suffix.removeprefix('.').upper()} · {size_text}"

    def _friendly_time(self, timestamp):
        # 时间按本机时区显示，不引入 tz-aware 的复杂度
        value = datetime.fromtimestamp(timestamp)  # noqa: DTZ006
        now = datetime.now()  # noqa: DTZ005

        if value.date() == now.date():
            return f"今天 {value.strftime('%H:%M')}"

        return value.strftime("%m-%d %H:%M")
