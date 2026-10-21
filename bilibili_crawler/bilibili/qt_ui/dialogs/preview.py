"""CSV/JSON 数据预览弹窗。"""

import re
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from bilibili_api import get_up_follower_count, get_video_info
from config import HOT_OUTPUT_DIR, SEARCH_OUTPUT_DIR
from qt_ui.dialogs.constants import (
    PREVIEW_ROW_LIMIT,
    TABLE_COLUMN_LIMIT,
    WRAP_ROW_LIMIT,
)
from qt_ui.dialogs.loaders import load_preview
from qt_ui.dialogs.models import (
    LinkItemDelegate,
    PreviewTableModel,
)
from qt_ui.formatting import (
    COLUMN_LABELS,
    KEY_COLUMN_ORDER,
    format_number,
    format_preview_value,
    shorten_user_hash,
)
from qt_ui.theme import (
    APP_STYLE,
    icon,
)


def detect_search_keyword(path):
    """从数据文件路径推断所属搜索关键词，非搜索数据返回 None。"""
    path = Path(path)

    if path.name == "hot_list.csv":
        return None

    parent = path.parent

    if parent.parent.name == SEARCH_OUTPUT_DIR.name:
        return parent.name

    if parent.parent.parent.name == HOT_OUTPUT_DIR.name:
        return parent.name

    return None


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
        raw_headers, headers, rows, truncated = load_preview(self.path)

        raw_headers, headers, rows = self._prioritize_columns(
            raw_headers,
            headers,
            rows,
        )
        self.preview_raw_headers = raw_headers

        try:
            modified_at = datetime.fromtimestamp(  # noqa: DTZ006
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
                    if raw_header in {"用户Hash", "哈希"}
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

        if header in {"ctime", "published_at", "发送时间"}:
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
        elif "内容" in raw_headers and (
            "弹幕池" in raw_headers
            or "出现时间" in raw_headers
            or "时间(ms)" in raw_headers
        ):
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
                ("视频编号", video_info.get("bvid") or "未知"),
                (
                    "视频时长",
                    format_preview_value(
                        "duration_seconds",
                        video_info.get("duration_seconds"),
                    )
                    or "未知",
                ),
            ],
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
                ("分区", video_info.get("partition") or "未知"),
                (
                    "投稿时间",
                    format_preview_value(
                        "published_at",
                        video_info.get("created_at"),
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

        # 封面地址很长，单独占一整行并允许选中复制
        cover_row = len(rows) + 1
        cover_label = QLabel("封面地址")
        cover_label.setObjectName("VideoInfoLabel")
        cover_value = QLabel(video_info.get("cover_url") or "未知")
        cover_value.setObjectName("VideoInfoValue")
        cover_value.setWordWrap(True)
        cover_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(cover_label, cover_row, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(cover_value, cover_row, 1, 1, 3)

        layout.setColumnStretch(1, 3)
        layout.setColumnStretch(3, 2)
        return panel

    def _open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


