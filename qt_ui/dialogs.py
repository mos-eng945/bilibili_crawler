"""Table preview and directory browser dialogs."""

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from output_paths import (
    OUTPUT_DIR,
    detect_search_keyword,
    is_subtitle_json,
    relative_display,
)
from qt_ui.formatting import (
    COLUMN_LABELS,
    KEY_COLUMN_ORDER,
    NUMBER_COLUMNS,
    format_number,
    format_preview_value,
    friendly_file_name,
    friendly_video_name,
    shorten_user_hash,
)
from qt_ui.theme import APP_STYLE, icon

PREVIEW_ROW_LIMIT = 5000
# 勾选「只显示关键列」时，表格保留最前面这些列
TABLE_COLUMN_LIMIT = 6
# 行数不超过这个值时，长文本换行完整显示（行数多则保持单行定高，避免卡顿）
WRAP_ROW_LIMIT = 200
# 这些后缀在数据浏览里可以直接预览，不再交给系统默认程序
BROWSABLE_SUFFIXES = {".csv", ".json", ".srt"}


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


class PreviewTableModel(QAbstractTableModel):
    """按需向表格视图提供数据，支持筛选和排序。"""

    def __init__(
        self,
        headers,
        rows,
        parent=None,
        full_rows=None,
        sort_keys=None,
        raw_headers=None,
    ):
        super().__init__(parent)
        self.headers = headers
        self.raw_headers = raw_headers or headers
        self._display = rows
        self._full = full_rows or rows
        self._sort = sort_keys or [list(row) for row in rows]
        self._view = list(range(len(self._display)))
        self._sort_column = None
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.numeric_columns = {
            index
            for index, header in enumerate(self.raw_headers)
            if header in NUMBER_COLUMNS
        }

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self._view)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = self._view[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display[row][column]

        if role == Qt.ItemDataRole.ToolTipRole:
            value = self._full[row][column]

            if self.raw_headers[column] == "cover_url":
                return f"点击打开封面\n{value}"

            return value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in self.numeric_columns:
                return int(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )

            return int(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

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
        if not self._view or column < 0 or column >= len(self.headers):
            return

        self._sort_column = column
        self._sort_order = order

        self.beginResetModel()
        self._apply_sort()
        self.endResetModel()

    def set_filter(self, text):
        """按关键字筛选，命中任意一列即保留。返回筛选后的行数。"""
        text = str(text or "").strip().casefold()

        self.beginResetModel()

        if not text:
            self._view = list(range(len(self._display)))
        else:
            self._view = [
                index
                for index, row in enumerate(self._display)
                if any(text in str(cell).casefold() for cell in row)
            ]

        self._apply_sort()
        self.endResetModel()
        return len(self._view)

    def _apply_sort(self):
        column = self._sort_column

        if column is None:
            return

        self._view.sort(
            key=lambda row: self._sort[row][column],
            reverse=self._sort_order == Qt.SortOrder.DescendingOrder,
        )

    def full_row(self, row):
        """返回视图第 `row` 行对应的完整内容（未经截断）。"""
        return self._full[self._view[row]]

    def full_value(self, row, column):
        return self._full[self._view[row]][column]


class SortableTableWidgetItem(QTableWidgetItem):
    """用显式排序键比较表格项，保证时间等字段按真实值排序。"""

    def __init__(self, text="", sort_key=None):
        super().__init__(text)
        self.sort_key = text.casefold() if sort_key is None else sort_key

    def __lt__(self, other):
        if not isinstance(other, SortableTableWidgetItem):
            return super().__lt__(other)

        return self.sort_key < other.sort_key


class LinkItemDelegate(QStyledItemDelegate):
    """给链接列增加颜色、下划线和悬浮反馈。"""

    link_column: int | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.link_column = None

    def paint(self, painter, option, index):
        if index.column() != self.link_column:
            super().paint(painter, option, index)
            return

        styled = QStyleOptionViewItem(option)
        font = styled.font
        font.setUnderline(True)
        styled.font = font
        hovered = bool(
            styled.state & QStyle.StateFlag.State_MouseOver
        )
        color = QColor("#e95482" if hovered else "#2f6feb")
        styled.palette.setColor(QPalette.ColorRole.Text, color)
        styled.palette.setColor(QPalette.ColorRole.HighlightedText, color)

        if hovered:
            styled.backgroundBrush = QBrush(QColor("#fff0f5"))

        super().paint(painter, styled, index)


class DataPreviewDialog(QDialog):
    """用中文列名和易读格式预览 CSV/JSON 数据。"""

    def __init__(self, path, parent=None, display_name=None):
        super().__init__(parent)
        self.path = Path(path)
        self.display_name = display_name or self.path.stem
        self.search_keyword = detect_search_keyword(self.path)
        self.bvid_column = None
        self.cover_column = None
        self._last_cover_open = (0.0, "")

        self.setWindowTitle(f"数据预览 - {self.display_name}")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(920, 600)
        self.setMinimumSize(720, 380)

        self.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

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

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("PreviewFilter")
        self.filter_edit.setPlaceholderText("筛选（匹配任意列）")
        self.filter_edit.setClearButtonEnabled(True)
        # 每敲一个字都重扫整表在几千行时会发卡，合并成 250ms 一次
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(
            lambda: self._apply_filter(self.filter_edit.text())
        )
        self.filter_edit.textChanged.connect(
            lambda *_: self._filter_timer.start(250)
        )
        filter_row.addWidget(self.filter_edit, 1)

        self.key_columns_only = QCheckBox("只显示关键列")
        self.key_columns_only.toggled.connect(
            self._apply_column_visibility
        )
        filter_row.addWidget(self.key_columns_only)
        layout.addLayout(filter_row)

        self.table = QTableView()
        self.table.setObjectName("DataPreviewTable")
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.link_delegate = LinkItemDelegate(self.table)
        self.table.setItemDelegate(self.link_delegate)
        self.table.clicked.connect(self._handle_cell_click)
        self.table.doubleClicked.connect(self._handle_cell_double_click)
        self.table.entered.connect(self._update_link_cursor)
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

        self._applying_widths = False
        self._columns_user_resized = False
        self.table.horizontalHeader().sectionResized.connect(
            self._handle_section_resized
        )

        footer = QHBoxLayout()
        self.row_hint = QLabel()
        self.row_hint.setObjectName("PreviewMeta")
        footer.addWidget(self.row_hint)
        footer.addStretch(1)

        self.open_video_button = QPushButton("打开视频")
        self.open_video_button.setIcon(icon("icon-play-dark.svg"))
        self.open_video_button.setEnabled(False)
        self.open_video_button.setToolTip(
            "打开当前选中行对应的 Bilibili 视频"
        )
        self.open_video_button.clicked.connect(
            self._open_selected_video
        )
        footer.addWidget(self.open_video_button)

        self.row_button = QPushButton("查看整行")
        self.row_button.setToolTip("列出当前选中行的全部字段")
        self.row_button.clicked.connect(self._show_row_detail)
        footer.addWidget(self.row_button)

        open_button = QPushButton("打开原始文件")
        open_button.setIcon(icon("icon-folder.svg"))
        open_button.clicked.connect(self._open_file)
        footer.addWidget(open_button)
        layout.addLayout(footer)

        self._load_data()

    def _load_data(self):
        suffix = self.path.suffix.lower()

        if suffix == ".csv":
            raw_headers, headers, rows, truncated = self._load_csv()
        elif suffix == ".json":
            raw_headers, headers, rows, truncated = self._load_json()
        elif suffix == ".srt":
            raw_headers, headers, rows, truncated = self._load_srt()
        else:
            raw_headers = ["字段", "内容"]
            headers = ["字段", "内容"]
            rows = []
            truncated = False

        raw_headers, headers, rows = self._prioritize_columns(
            raw_headers,
            headers,
            rows,
        )
        self.preview_raw_headers = raw_headers

        try:
            modified_at = datetime.fromtimestamp(
                self.path.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M")
        except OSError:
            modified_at = "未知"

        row_count_text = f"{len(rows)} 行"

        if truncated:
            row_count_text += f"（仅预览前 {PREVIEW_ROW_LIMIT} 行）"

        self.meta.setText(
            f"{row_count_text} · {suffix.removeprefix('.').upper()} · "
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
            raw_headers=raw_headers,
        )
        self.table.setModel(self.preview_model)
        self.bvid_column = (
            self.preview_raw_headers.index("bvid")
            if "bvid" in self.preview_raw_headers
            else None
        )
        self.cover_column = (
            self.preview_raw_headers.index("cover_url")
            if "cover_url" in self.preview_raw_headers
            else None
        )
        self.link_delegate.link_column = self.cover_column
        self.open_video_button.setVisible(self.bvid_column is not None)
        self.table.selectionModel().currentRowChanged.connect(
            self._update_open_video_state
        )
        self._update_open_video_state()
        self._total_rows = len(rows)
        self._base_row_hint = (
            row_count_text
            if not truncated
            else f"{row_count_text}，完整数据请打开原始文件"
        )
        self.row_hint.setText(self._base_row_hint)
        self.filter_edit.blockSignals(True)
        self.filter_edit.clear()
        self.filter_edit.blockSignals(False)

        self._base_column_widths = [
            self._preview_column_width(header)
            for header in headers
        ]
        stretch_headers = {
            "评论内容",
            "评论时间",
            "弹幕内容",
            "字幕内容",
            "标签",
            "标题",
            "简介",
            "热搜词",
        }
        self._preferred_stretch_indexes = [
            index
            for index, header in enumerate(headers)
            if header in stretch_headers
        ]
        self._apply_column_visibility()
        self._apply_row_wrapping()

        if self._populate_video_overview(raw_headers, rows):
            self.table.hide()
            self.filter_edit.hide()
            self.key_columns_only.hide()
            self.row_button.hide()
            self.row_hint.hide()
            self.open_video_button.hide()
        else:
            self._fit_height_to_rows()

    def _apply_column_visibility(self, key_only=False):
        """默认显示全部列；勾选「只显示关键列」时才收起后面的列。"""
        if not hasattr(self, "preview_model"):
            return

        total = self.preview_model.columnCount()
        visible_count = min(total, TABLE_COLUMN_LIMIT) if key_only else total

        for index in range(total):
            self.table.setColumnHidden(index, index >= visible_count)

        visible = set(range(visible_count))
        stretch = [
            index
            for index in self._preferred_stretch_indexes
            if index in visible
        ]

        if not stretch and visible_count:
            stretch = [visible_count - 1]

        self._stretch_column_indexes = stretch
        self._columns_user_resized = False
        self._apply_preview_column_widths()

    def _fit_height_to_rows(self):
        """行数不多时把窗口高度收到内容大小，避免大片空白。"""
        rows = self.preview_model.rowCount()

        if not rows or rows > 20:
            return

        row_height = self.table.verticalHeader().defaultSectionSize()
        body = 0

        for index in range(rows):
            body += max(row_height, self.table.sizeHintForRow(index))

        target = max(320, 240 + body)

        if target < self.height():
            self.resize(self.width(), target)

    def _apply_row_wrapping(self):
        """行数少时长文本换行显示完整内容，行数多时保持单行定高。"""
        wrap = self.preview_model.rowCount() <= WRAP_ROW_LIMIT
        header = self.table.verticalHeader()

        self.table.setWordWrap(wrap)

        if wrap:
            header.setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            header.setDefaultSectionSize(30)

    def _apply_filter(self, text):
        if not hasattr(self, "preview_model"):
            return

        shown = self.preview_model.set_filter(text)

        if shown == self._total_rows:
            self.row_hint.setText(self._base_row_hint)
        else:
            self.row_hint.setText(
                f"筛选出 {shown} / {self._total_rows} 行"
            )

        self._update_open_video_state()

    def _handle_section_resized(self, index, old_size, new_size):
        if not self._applying_widths:
            self._columns_user_resized = True

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
                    timestamp = datetime.fromisoformat(text).timestamp()

                return (0, 0.0, timestamp)
            except (ValueError, OSError):
                pass

        return (1, 0.0, text.casefold())

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

        # 时间列要放得下 "2025-09-30 22:40"，窄了会被省略号截掉
        if header in {"评论时间", "发布时间"}:
            return 150

        if header in {"用户", "作者", "UP 主", "UP主"}:
            return 130

        if header in {
            "图片地址",
            "封面地址",
            "标签",
            "结果文件",
            "开始时间",
            "结束时间",
        }:
            return 220

        return max(90, min(180, len(str(header)) * 16 + 36))

    def _apply_preview_column_widths(self):
        if not self._base_column_widths or self._columns_user_resized:
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

        self._applying_widths = True

        try:
            for index, width in enumerate(widths):
                if self.table.columnWidth(index) != width:
                    self.table.setColumnWidth(index, width)
        finally:
            self._applying_widths = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_preview_column_widths)

    def _handle_cell_double_click(self, index):
        if not index.isValid():
            return

        header = self.preview_model.headers[index.column()]

        if header == "封面地址":
            self._open_cover_for_index(index)
            return

        if (
            self.bvid_column is not None
            and header in {"视频编号", "标题"}
            and self._open_video_for_row(index.row())
        ):
            return

        self._show_cell_detail(index)

    def _handle_cell_click(self, index):
        if self._is_cover_index(index):
            self._open_cover_for_index(index)

    def _update_link_cursor(self, index):
        if self._is_cover_index(index):
            self.table.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor
            )
        else:
            self.table.viewport().unsetCursor()

    def _is_cover_index(self, index):
        return (
            self.cover_column is not None
            and index.isValid()
            and index.column() == self.cover_column
        )

    def _open_cover_for_index(self, index):
        if not self._is_cover_index(index):
            return False

        url = self.preview_model.full_value(
            index.row(),
            index.column(),
        ).strip()

        if not url.startswith(("http://", "https://")):
            return False

        now = time.monotonic()

        if (
            url == self._last_cover_open[1]
            and now - self._last_cover_open[0] < 0.5
        ):
            return True

        self._last_cover_open = (now, url)
        QDesktopServices.openUrl(QUrl(url))
        return True

    def _update_open_video_state(self, *_):
        current = self.table.currentIndex()
        enabled = (
            self.bvid_column is not None
            and current.isValid()
            and bool(self._bvid_for_row(current.row()))
        )
        self.open_video_button.setEnabled(enabled)

    def _open_selected_video(self):
        current = self.table.currentIndex()

        if current.isValid():
            self._open_video_for_row(current.row())

    def _open_video_for_row(self, row):
        bvid = self._bvid_for_row(row)

        if not bvid:
            return False

        QDesktopServices.openUrl(
            QUrl(f"https://www.bilibili.com/video/{bvid}")
        )
        return True

    def _bvid_for_row(self, row):
        if (
            self.bvid_column is None
            or row < 0
            or row >= self.preview_model.rowCount()
        ):
            return ""

        bvid = self.preview_model.full_value(
            row,
            self.bvid_column,
        ).strip()

        return bvid if re.fullmatch(r"BV[0-9A-Za-z]+", bvid) else ""

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
        self._show_text_dialog(f"{header} - 完整内容", full_text)

    def _show_row_detail(self):
        """列出选中行的全部字段，弥补表格只显示关键列。"""
        index = self.table.currentIndex()

        if not index.isValid():
            QMessageBox.information(
                self,
                "查看整行",
                "请先在表格中选择一行。",
            )
            return

        headers = self.preview_model.raw_headers
        values = self.preview_model.full_row(index.row())
        lines = [
            f"{COLUMN_LABELS.get(header, header)}：{value}"
            for header, value in zip(headers, values)
        ]
        self._show_text_dialog("整行内容", "\n".join(lines))

    def _show_text_dialog(self, title, text):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(*self._detail_dialog_size(text))
        dialog.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        editor = QPlainTextEdit(text)
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

    @staticmethod
    def _detail_dialog_size(text):
        lines = text.splitlines() or [""]
        line_count = len(lines)
        longest_line = max(len(line) for line in lines)

        if line_count <= 3 and longest_line <= 80:
            width = min(620, max(320, longest_line * 10 + 100))
            height = max(168, 110 + line_count * 26)
            return width, height

        return 720, 460

    def _load_csv(self):
        rows = []
        truncated = False

        with open(self.path, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            raw_headers = reader.fieldnames or []
            headers = [
                COLUMN_LABELS.get(header, header)
                for header in raw_headers
            ]

            for row in reader:
                if len(rows) >= PREVIEW_ROW_LIMIT:
                    truncated = True
                    break

                rows.append(
                    [
                        str(row.get(header) or "").replace("\x00", "")
                        for header in raw_headers
                    ]
                )

        return raw_headers, headers, rows, truncated

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
            rows = []
            truncated = False

            for index, item in enumerate(body, start=1):
                if len(rows) >= PREVIEW_ROW_LIMIT:
                    truncated = True
                    break

                rows.append(
                    [
                        index,
                        item.get("from", 0),
                        item.get("to", 0),
                        item.get("content", ""),
                    ]
                )

            return raw_headers, headers, rows, truncated

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

        return raw_headers, headers, rows, False

    def _load_srt(self):
        """把 SRT 字幕拆成序号/开始/结束/内容四列。"""
        raw_headers = ["序号", "开始", "结束", "字幕内容"]
        headers = ["序号", "开始时间", "结束时间", "字幕内容"]
        rows = []
        truncated = False
        text = self.path.read_text(encoding="utf-8-sig", errors="replace")

        for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
            if len(rows) >= PREVIEW_ROW_LIMIT:
                truncated = True
                break

            lines = [line for line in block.splitlines() if line.strip()]

            if len(lines) < 3:
                continue

            match = re.match(
                r"(.+?)\s*-->\s*(.+)",
                lines[1],
            )
            start, end = (
                (match.group(1).strip(), match.group(2).strip())
                if match
                else ("", "")
            )
            rows.append(
                [len(rows) + 1, start, end, "\n".join(lines[2:])]
            )

        return raw_headers, headers, rows, truncated

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

        # 标题单独占一整行，避免长标题被列宽切掉
        title_label = QLabel("视频标题")
        title_label.setObjectName("VideoInfoLabel")
        title_value = QLabel(str(video_info.get("title") or "未知"))
        title_value.setObjectName("VideoInfoValue")
        title_value.setWordWrap(True)
        title_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(title_label, 0, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title_value, 0, 1, 1, 3)

        rows = [
            [
                ("UP 主", video_info.get("up_name") or "未知"),
                (
                    "发布时间",
                    format_preview_value(
                        "published_at",
                        video_info.get("published_at"),
                    )
                    or "未知",
                ),
            ],
            [
                ("播放量", format_number(video_info.get("view"))),
                ("点赞", format_number(video_info.get("like"))),
            ],
            [
                ("评论", format_number(video_info.get("reply"))),
                ("收藏", format_number(video_info.get("favorite"))),
            ],
            [
                ("弹幕", format_number(video_info.get("danmaku"))),
                ("硬币", format_number(video_info.get("coin"))),
            ],
            [
                ("分享", format_number(video_info.get("share"))),
                (
                    "UP 主粉丝",
                    format_number(video_info.get("up_follower_count")),
                ),
            ],
        ]

        for row_index, row in enumerate(rows, start=1):
            for column_index, (label_text, value_text) in enumerate(row):
                base_column = column_index * 2

                label = QLabel(label_text)
                label.setObjectName("VideoInfoLabel")
                value = QLabel(str(value_text))
                value.setObjectName("VideoInfoValue")
                value.setWordWrap(True)

                layout.addWidget(label, row_index, base_column)
                layout.addWidget(value, row_index, base_column + 1)

        layout.setColumnStretch(1, 3)
        layout.setColumnStretch(3, 2)
        return panel

    def _open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


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
        value = datetime.fromtimestamp(timestamp)
        now = datetime.now()

        if value.date() == now.date():
            return f"今天 {value.strftime('%H:%M')}"

        return value.strftime("%m-%d %H:%M")
