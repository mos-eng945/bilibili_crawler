"""Table preview and directory browser dialogs."""

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bilibili_api import BASE_DIR
from qt_ui.formatting import (
    COLUMN_LABELS,
    KEY_COLUMN_ORDER,
    format_number,
    format_preview_value,
    shorten_user_hash,
)
from qt_ui.theme import APP_STYLE


class CompletionDialog(QDialog):
    """任务完成后的统一提示框。"""

    def __init__(self, task_name, path=None, parent=None):
        super().__init__(parent)
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
            try:
                display_path = (
                    "output/"
                    + path.relative_to(BASE_DIR / "output").as_posix()
                )
            except ValueError:
                display_path = str(path)

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
            open_button = QPushButton("打开")
            open_button.setMinimumWidth(88)
            open_button.clicked.connect(
                lambda: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(path))
                )
            )
            actions.addWidget(open_button)

        close_button = QPushButton("完成")
        close_button.setObjectName("PrimaryButton")
        close_button.setMinimumWidth(96)
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)


class PreviewTableModel(QAbstractTableModel):
    """按需向表格视图提供数据，避免为每一行创建单元格对象。"""

    def __init__(
        self,
        headers,
        rows,
        parent=None,
        full_rows=None,
        sort_keys=None,
    ):
        super().__init__(parent)
        self.headers = headers
        self.rows = rows
        self.full_rows = full_rows or rows
        self.sort_keys = sort_keys or [list(row) for row in rows]

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self.rows[index.row()][index.column()]

        if role == Qt.ItemDataRole.ToolTipRole:
            return self.full_rows[index.row()][index.column()]

        return None

    def headerData(
        self,
        section,
        orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section]

        return section + 1

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if (
            not self.rows
            or column < 0
            or column >= len(self.headers)
        ):
            return

        indexes = sorted(
            range(len(self.rows)),
            key=lambda row_index: self.sort_keys[row_index][column],
            reverse=order == Qt.SortOrder.DescendingOrder,
        )

        self.beginResetModel()
        self.rows = [self.rows[index] for index in indexes]
        self.full_rows = [self.full_rows[index] for index in indexes]
        self.sort_keys = [self.sort_keys[index] for index in indexes]
        self.endResetModel()


class SortableTableWidgetItem(QTableWidgetItem):
    """用显式排序键比较表格项，保证时间等字段按真实值排序。"""

    def __init__(self, text="", sort_key=None):
        super().__init__(text)
        self.sort_key = text.casefold() if sort_key is None else sort_key

    def __lt__(self, other):
        if not isinstance(other, SortableTableWidgetItem):
            return super().__lt__(other)

        return self.sort_key < other.sort_key


class DataPreviewDialog(QDialog):
    """用中文列名和易读格式预览 CSV/JSON 数据。"""

    def __init__(self, path, parent=None, display_name=None):
        super().__init__(parent)
        self.path = Path(path)
        self.display_name = display_name or self.path.stem
        self.search_keyword = self._detect_search_keyword()

        self.setWindowTitle(f"数据预览 - {self.display_name}")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(920, 600)

        self.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel(f"数据预览 - {self.display_name}")
        title.setObjectName("PreviewTitle")
        layout.addWidget(title)

        self.meta = QLabel("正在读取数据...")
        self.meta.setObjectName("PreviewMeta")
        self.meta.setToolTip(str(self.path))
        self.meta.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.meta)

        self.video_overview = QWidget()
        self.video_overview_layout = QVBoxLayout(self.video_overview)
        self.video_overview_layout.setContentsMargins(0, 0, 0, 0)
        self.video_overview_layout.setSpacing(10)
        self.video_overview.hide()
        layout.addWidget(self.video_overview)

        self.table = QTableView()
        self.table.setObjectName("DataPreviewTable")
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._show_cell_detail)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.horizontalHeader().sectionClicked.connect(
            self._sort_preview
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.row_hint = QLabel()
        self.row_hint.setObjectName("PreviewMeta")
        footer.addWidget(self.row_hint)
        footer.addStretch(1)

        self.detail_button = QPushButton("查看完整内容")
        self.detail_button.clicked.connect(
            lambda: self._show_cell_detail()
        )
        footer.addWidget(self.detail_button)

        open_button = QPushButton("打开原始文件")
        open_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        open_button.clicked.connect(self._open_file)
        footer.addWidget(open_button)
        layout.addLayout(footer)

        self._load_data()

    def _load_data(self):
        suffix = self.path.suffix.lower()

        if suffix == ".csv":
            raw_headers, headers, rows = self._load_csv()
        elif suffix == ".json":
            raw_headers, headers, rows = self._load_json()
        else:
            raw_headers = ["字段", "内容"]
            headers = ["字段", "内容"]
            rows = []

        raw_headers, headers, rows = self._prioritize_columns(
            raw_headers,
            headers,
            rows,
        )
        self.preview_raw_headers = raw_headers

        try:
            modified_at = datetime.fromtimestamp(
                self.path.stat().st_mtime
            ).strftime("%m-%d %H:%M")
        except OSError:
            modified_at = "未知"

        self.meta.setText(
            f"{len(rows)} 行 · {suffix.removeprefix('.').upper()} · "
            f"更新于 {modified_at}"
            + (
                f" · 关键词：{self.search_keyword}"
                if self.search_keyword
                else ""
            )
        )

        display_rows = []
        full_rows = []
        sort_keys = []

        for row in rows:
            display_row = []
            full_row = []
            sort_row = []

            for column_index, raw_value in enumerate(row):
                raw_header = raw_headers[column_index]

                if raw_headers == ["字段", "内容"]:
                    value = format_preview_value(raw_header, raw_value)

                    if column_index == 0:
                        value = COLUMN_LABELS.get(raw_value, str(raw_value))
                    elif column_index == 1 and row:
                        value = format_preview_value(row[0], raw_value)
                else:
                    value = format_preview_value(raw_header, raw_value)

                full_value = str(value)
                full_row.append(full_value)
                display_row.append(
                    shorten_user_hash(full_value)
                    if raw_header == "用户Hash"
                    else full_value
                )
                sort_row.append(
                    self._preview_sort_key(raw_header, raw_value)
                )

            display_rows.append(display_row)
            full_rows.append(full_row)
            sort_keys.append(sort_row)

        self.preview_model = PreviewTableModel(
            headers,
            display_rows,
            self,
            full_rows=full_rows,
            sort_keys=sort_keys,
        )
        self.table.setModel(self.preview_model)
        self.row_hint.setText(f"共 {len(rows)} 行")

        self._base_column_widths = [
            self._preview_column_width(header)
            for header in headers
        ]
        stretch_headers = {
            "评论内容",
            "评论时间",
            "弹幕内容",
            "字幕内容",
            "标题",
            "简介",
            "热搜词",
        }
        self._stretch_column_indexes = [
            index
            for index, header in enumerate(headers)
            if header in stretch_headers
        ]

        if not self._stretch_column_indexes and headers:
            self._stretch_column_indexes = [len(headers) - 1]

        self._apply_preview_column_widths()

        if self._populate_video_overview(raw_headers, rows):
            self.table.hide()
            self.detail_button.hide()
            self.row_hint.hide()

    def _sort_preview(self, column):
        header = self.table.horizontalHeader()
        order = Qt.SortOrder.AscendingOrder

        if (
            header.sortIndicatorSection() == column
            and header.sortIndicatorOrder()
            == Qt.SortOrder.AscendingOrder
        ):
            order = Qt.SortOrder.DescendingOrder

        self.preview_model.sort(column, order)
        header.setSortIndicator(column, order)
        header.setSortIndicatorShown(True)

    @staticmethod
    def _preview_sort_key(header, value):
        text = str(value if value is not None else "").strip()

        if not text:
            return (2, 0.0, "")

        numeric_text = text.replace(",", "")

        try:
            return (0, 0.0, float(numeric_text))
        except ValueError:
            pass

        if header in {"ctime", "published_at"}:
            try:
                if header == "ctime":
                    timestamp = float(numeric_text)
                else:
                    timestamp = datetime.fromisoformat(
                        text.replace("Z", "+00:00")
                    ).timestamp()

                return (0, 0.0, timestamp)
            except (ValueError, OSError):
                pass

        return (1, 0.0, text.casefold())

    def _detect_search_keyword(self):
        if self.path.name == "hot_list.csv":
            return None

        parent = self.path.parent

        if parent.parent.name == "search":
            return parent.name

        if parent.parent.parent.name == "hot-search":
            return parent.name

        return None

    def _prioritize_columns(self, raw_headers, headers, rows):
        if "play_count" in raw_headers and "title" in raw_headers:
            key_order = KEY_COLUMN_ORDER["search"]
        elif "rpid" in raw_headers and "message" in raw_headers:
            key_order = KEY_COLUMN_ORDER["comments"]
        elif "heat_score" in raw_headers and "keyword" in raw_headers:
            key_order = KEY_COLUMN_ORDER["hot_search"]
        elif "时间(ms)" in raw_headers and "内容" in raw_headers:
            key_order = KEY_COLUMN_ORDER["danmaku"]
        elif "view" in raw_headers and "up_name" in raw_headers:
            key_order = KEY_COLUMN_ORDER["video_info"]
        else:
            return raw_headers, headers, rows

        ordered = [header for header in key_order if header in raw_headers]
        ordered.extend(
            header for header in raw_headers if header not in ordered
        )
        indexes = [raw_headers.index(header) for header in ordered]

        return (
            ordered,
            [headers[index] for index in indexes],
            [[row[index] for index in indexes] for row in rows],
        )

    def _preview_column_width(self, header):
        if header in {"评论内容", "字幕内容", "标题", "简介"}:
            return 360

        if {"heat_score", "keyword"}.issubset(
            self.preview_raw_headers
        ):
            if header == "热搜词":
                return 220

            if header == "结果文件":
                return 120

            if header == "错误":
                return 72

        if (
            {"rpid", "message"}.issubset(self.preview_raw_headers)
            and header in {"点赞", "回复数", "等级", "评论状态"}
        ):
            return 60

        if header in {
            "图片地址",
            "结果文件",
            "开始时间",
            "结束时间",
        }:
            return 220

        return max(90, min(180, len(str(header)) * 16 + 36))

    def _apply_preview_column_widths(self):
        if not self._base_column_widths:
            return

        base_widths = self._base_column_widths
        base_total = sum(base_widths)
        available_width = max(
            self.table.viewport().width(),
            base_total,
        )
        extra_width = available_width - base_total
        widths = list(base_widths)

        if extra_width and self._stretch_column_indexes:
            stretch_indexes = self._stretch_column_indexes
            stretch_total = sum(
                base_widths[index]
                for index in stretch_indexes
            )
            distributed = 0

            for index in stretch_indexes[:-1]:
                share = round(
                    extra_width * base_widths[index] / stretch_total
                )
                widths[index] += share
                distributed += share

            widths[stretch_indexes[-1]] += (
                extra_width - distributed
            )

        for index, width in enumerate(widths):
            if self.table.columnWidth(index) != width:
                self.table.setColumnWidth(index, width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_preview_column_widths)

    def _show_cell_detail(self, index=None):
        if index is None or not index.isValid():
            index = self.table.currentIndex()

        if not index.isValid():
            QMessageBox.information(
                self,
                "查看完整内容",
                "请先在表格中选择一个单元格。",
            )
            return

        header = self.preview_model.headers[index.column()]
        value = self.preview_model.data(
            index,
            Qt.ItemDataRole.ToolTipRole,
        )
        full_text = str(value or "").replace(r"\n", "\n")

        dialog = QDialog(self)
        dialog.setWindowTitle(f"{header} - 完整内容")
        dialog.resize(720, 460)
        dialog.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        editor = QPlainTextEdit(full_text)
        editor.setObjectName("FullContentEdit")
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(editor, 1)

        close_button = QPushButton("关闭")
        close_button.setObjectName("PrimaryButton")
        close_button.clicked.connect(dialog.accept)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        dialog.exec()

    def _load_csv(self):
        rows = []

        with open(self.path, "r", newline="", encoding="utf-8-sig") as file:
            content = file.read().replace("\x00", "")

        reader = csv.DictReader(io.StringIO(content))
        raw_headers = reader.fieldnames or []
        headers = [
            COLUMN_LABELS.get(header, header)
            for header in raw_headers
        ]

        for row in reader:
            rows.append([row.get(header, "") for header in raw_headers])

        return raw_headers, headers, rows

    def _load_json(self):
        with open(self.path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict) and isinstance(
            data.get("subtitle"),
            dict,
        ):
            subtitle = data.get("subtitle") or {}
            body = subtitle.get("body") or []
            raw_headers = ["序号", "开始", "结束", "字幕内容"]
            headers = ["序号", "开始时间", "结束时间", "字幕内容"]
            rows = [
                [
                    index,
                    item.get("from", 0),
                    item.get("to", 0),
                    item.get("content", ""),
                ]
                for index, item in enumerate(body, start=1)
            ]
            return raw_headers, headers, rows

        if isinstance(data, dict):
            raw_headers = list(data.keys())
            headers = [
                COLUMN_LABELS.get(key, key)
                for key in raw_headers
            ]
            row = []

            for key in raw_headers:
                value = data.get(key)

                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)

                row.append(value)

            rows = [row]
        else:
            raw_headers = ["字段", "内容"]
            headers = ["字段", "内容"]
            rows = []

        return raw_headers, headers, rows

    def _populate_video_overview(self, raw_headers, rows):
        if self.path.name != "video_info.json" or not rows:
            return False

        data = dict(zip(raw_headers, rows[0]))
        section = QLabel("视频信息")
        section.setObjectName("ReportSection")
        self.video_overview_layout.addWidget(section)
        self.video_overview_layout.addWidget(
            self._build_video_info_panel(data)
        )

        description_section = QLabel("视频简介")
        description_section.setObjectName("ReportSection")
        self.video_overview_layout.addWidget(description_section)

        description = QPlainTextEdit(
            data.get("description") or "暂无简介"
        )
        description.setObjectName("VideoDescription")
        description.setReadOnly(True)
        description.setMinimumHeight(100)
        description.setMaximumHeight(180)
        description.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.video_overview_layout.addWidget(description)
        self.video_overview.show()
        return True

    def _build_video_info_panel(self, video_info):
        panel = QFrame()
        panel.setObjectName("VideoInfoPanel")

        layout = QGridLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        rows = [
            [
                ("视频标题", video_info.get("title") or "未知"),
                ("UP 主", video_info.get("up_name") or "未知"),
            ],
            [
                (
                    "发布时间",
                    format_preview_value(
                        "published_at",
                        video_info.get("published_at"),
                    )
                    or "未知",
                ),
                ("播放量", format_number(video_info.get("view"))),
            ],
            [
                ("点赞", format_number(video_info.get("like"))),
                ("评论", format_number(video_info.get("reply"))),
            ],
            [
                ("收藏", format_number(video_info.get("favorite"))),
                ("弹幕", format_number(video_info.get("danmaku"))),
            ],
            [
                ("硬币", format_number(video_info.get("coin"))),
                ("分享", format_number(video_info.get("share"))),
            ],
        ]

        for row_index, row in enumerate(rows):
            for column_index, (label_text, value_text) in enumerate(row):
                base_column = column_index * 2

                label = QLabel(label_text)
                label.setObjectName("VideoInfoLabel")
                value = QLabel(str(value_text))
                value.setObjectName("VideoInfoValue")
                value.setWordWrap(True)

                layout.addWidget(label, row_index, base_column)
                layout.addWidget(value, row_index, base_column + 1)

        follower_row = len(rows)
        follower_label = QLabel("UP 主粉丝")
        follower_label.setObjectName("VideoInfoLabel")
        follower_value = QLabel(
            format_number(video_info.get("up_follower_count"))
        )
        follower_value.setObjectName("VideoInfoValue")
        layout.addWidget(follower_label, follower_row, 0)
        layout.addWidget(follower_value, follower_row, 1, 1, 3)

        layout.setColumnStretch(1, 3)
        layout.setColumnStretch(3, 2)
        return panel

    def _open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


class DataBrowserDialog(QDialog):
    """按 output 目录层级浏览数据。"""

    def __init__(self, parent=None, initial_path=None):
        super().__init__(parent)
        self.output_dir = BASE_DIR / "output"
        self.root_dir = self.output_dir
        self.current_dir = self.root_dir
        self.browser_entries = []
        self.browser_sort_column = 2
        self.browser_sort_order = Qt.SortOrder.DescendingOrder

        self.setWindowTitle("数据查看")
        self.resize(920, 620)
        self.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("数据查看")
        title.setObjectName("PreviewTitle")
        layout.addWidget(title)

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
        self.browser_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self.browser_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.browser_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
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
        self.parent_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        )
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
                    display_name=self._friendly_file_name(data_file),
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
            elif path.suffix.lower() in {".csv", ".json"}:
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
                name = self._friendly_folder_name(path.name)
                summary = self._directory_summary(path)
            else:
                name = self._friendly_file_name(path)
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

        if path.suffix.lower() in {".csv", ".json"}:
            DataPreviewDialog(
                path,
                self,
                display_name=self._friendly_file_name(path),
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

        root_item = QTreeWidgetItem(
            ["output", str(self._count_data_files(self.output_dir))]
        )
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self.output_dir))
        self.directory_tree.addTopLevelItem(root_item)
        self._add_tree_children(root_item, self.output_dir)
        root_item.setExpanded(True)

    def _add_tree_children(self, parent_item, directory):
        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_dir() or path.name == "__pycache__":
                continue

            item = QTreeWidgetItem(
                [path.name, str(self._count_data_files(path))]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            parent_item.addChild(item)
            self._add_tree_children(item, path)

    def _open_tree_directory(self, item):
        path_text = item.data(0, Qt.ItemDataRole.UserRole)

        if path_text:
            self._navigate_to(Path(path_text))

    def _friendly_folder_name(self, name):
        parts = name.rsplit("_", 1)

        if len(parts) != 2 or not parts[1].startswith("BV"):
            return name

        base_name = parts[0]

        if "_" in base_name:
            up_name, title = base_name.split("_", 1)
            return f"{title} · {up_name}"

        return base_name

    def _friendly_file_name(self, path):
        filename = path.name

        if filename == "video_info.json":
            return "视频概览"

        if filename.startswith("comments_"):
            return "评论"

        if filename.startswith("danmaku_"):
            match = re.search(r"_p(\d+)\.csv$", filename)
            return f"弹幕 P{match.group(1)}" if match else "弹幕"

        if filename.startswith("subtitle_"):
            match = re.search(r"_p(\d+)_(.+)\.json$", filename)

            if match:
                return f"字幕 P{match.group(1)} · {match.group(2)}"

            return "字幕"

        if filename == "hot_list.csv":
            return "热搜汇总"

        if filename.startswith("search_"):
            keyword = path.parent.name
            parts = path.stem.rsplit("_", 1)
            count_text = ""

            if len(parts) == 2 and parts[1].isdigit():
                count_text = f" · {parts[1]} 条"

            return f"搜索结果 · {keyword}{count_text}"

        if filename.startswith("videos_"):
            parts = path.stem.rsplit("_", 1)
            count_text = ""

            if len(parts) == 2 and parts[1].isdigit():
                count_text = f" · {parts[1]} 条"

            return f"UP 主视频{count_text}"

        return path.stem

    def _directory_summary(self, path):
        child_dirs = 0
        direct_files = 0

        try:
            for child in path.iterdir():
                if child.is_dir():
                    child_dirs += 1
                elif child.suffix.lower() in {".csv", ".json"}:
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

    def _count_data_files(self, directory):
        count = 0

        try:
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".csv", ".json"}:
                    count += 1
        except OSError:
            return 0

        return count

    def _friendly_time(self, timestamp):
        value = datetime.fromtimestamp(timestamp)
        now = datetime.now()

        if value.date() == now.date():
            return f"今天 {value.strftime('%H:%M')}"

        return value.strftime("%m-%d %H:%M")
