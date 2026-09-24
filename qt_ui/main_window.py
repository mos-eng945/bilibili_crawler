"""Main Qt window and crawler process control."""

import re
import sys

from PySide6.QtCore import (
    QLocale,
    QProcess,
    QProcessEnvironment,
    QRectF,
    QSize,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bilibili_api import BASE_DIR
from crawler_common import SEARCH_DEFAULT_WORKERS, SEARCH_MAX_WORKERS
from config import DEFAULT_BVID, parse_page_range
from qt_ui.dialogs import CompletionDialog, DataBrowserDialog
from qt_ui.theme import APP_STYLE

BVID_PATTERN = re.compile(r"^BV[0-9A-Za-z]+$")
LOGIN_PROMPT = "登录完成后按回车"


class MainWindow(QMainWindow):
    """组织任务参数并通过 QProcess 调用命令行入口。"""

    def __init__(self):
        super().__init__()
        self._process = None
        self._busy = False
        self._login_prompt_seen = False
        self._scan_buffer = ""
        self._task_title = ""
        self._task_page = 0
        self._start_buttons = []
        self._nav_buttons = []
        self._project_data_panels = []
        self._recent_cache = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._refresh_recent_outputs)

        self.setWindowTitle("Bilibili 数据采集器")
        self.setWindowIcon(self._app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(1060, 740)

        self._build_ui()
        self._apply_style()
        self._update_video_controls()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        body = QWidget()
        body.setObjectName("Body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.sidebar = self._build_sidebar()
        body_layout.addWidget(self.sidebar)
        self.sidebar_rail = self._build_sidebar_rail()
        body_layout.addWidget(self.sidebar_rail)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(22, 18, 22, 16)
        workspace_layout.setSpacing(14)

        title_row = QHBoxLayout()
        self.page_title = QLabel("视频采集")
        self.page_title.setObjectName("PageTitle")
        title_row.addWidget(self.page_title)
        title_row.addStretch(1)

        workspace_layout.addLayout(title_row)

        self.metric_strip = QHBoxLayout()
        self.metric_strip.setSpacing(10)
        status_card, self.metric_status_value = self._make_metric_card(
            "运行状态",
            "空闲",
            accent=True,
        )
        login_card, self.metric_login_value = self._make_metric_card(
            "登录状态",
            "待检查",
        )
        data_card, self.metric_data_value = self._make_metric_card(
            "数据文件",
            "0",
        )
        data_card.setFixedWidth(230)
        self.metric_strip.addWidget(status_card)
        self.metric_strip.addWidget(login_card)
        self.metric_strip.addWidget(data_card)
        workspace_layout.addLayout(self.metric_strip)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_video_tab())
        self.pages.addWidget(self._build_search_tab())
        self.pages.addWidget(self._build_user_video_tab())
        self.pages.addWidget(self._build_hot_search_tab())
        self.pages.addWidget(self._build_log_tab())
        workspace_layout.addWidget(self.pages, 1)
        body_layout.addWidget(workspace, 1)
        root_layout.addWidget(body, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress, 1)
        self.statusBar().showMessage("就绪")
        self._switch_page(0)
        self._refresh_recent_outputs()

    def _load_rounded_pixmap(self, filename, size, radius):
        source = QPixmap(str(BASE_DIR / "assets" / filename))

        if source.isNull():
            return source

        scaled = source.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = max(0, (scaled.width() - size.width()) // 2)
        top = max(0, (scaled.height() - size.height()) // 2)
        cropped = scaled.copy(left, top, size.width(), size.height())

        rounded = QPixmap(size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(
            QRectF(0, 0, size.width(), size.height()),
            radius,
            radius,
        )
        painter.setClipPath(clip_path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    @staticmethod
    def _app_icon():
        return QIcon(str(BASE_DIR / "assets" / "app-icon.svg"))

    def _build_header(self):
        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(78)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        logo = QLabel("B")
        logo.setObjectName("LogoBadge")
        logo.setFixedSize(42, 42)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = self._load_rounded_pixmap(
            "app-icon.svg",
            QSize(42, 42),
            10,
        )

        if not logo_pixmap.isNull():
            logo.setText("")
            logo.setPixmap(logo_pixmap)

        layout.addWidget(logo)

        title_block = QVBoxLayout()
        title_block.setSpacing(0)
        title = QLabel("Bilibili 数据采集器")
        title.setObjectName("AppTitle")
        title_block.addWidget(title)
        caption = QLabel("DATA COLLECTION STUDIO")
        caption.setObjectName("AppCaption")
        title_block.addWidget(caption)
        layout.addLayout(title_block)
        layout.addStretch(1)

        self.login_button = QPushButton("检查登录")
        self.login_button.setObjectName("HeaderButton")
        self.login_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        )
        self.login_button.clicked.connect(self._check_login)
        layout.addWidget(self.login_button)

        return header

    def _build_sidebar_rail(self):
        rail = QWidget()
        rail.setObjectName("SidebarRail")
        rail.setFixedWidth(20)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        self.sidebar_toggle = QPushButton()
        self.sidebar_toggle.setObjectName("RailButton")
        self.sidebar_toggle.setFixedSize(20, 38)
        self.sidebar_toggle.setText("‹")
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.setToolTip("隐藏导航")
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        return rail

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(214)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(8)

        section = QLabel("工作区")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        nav_items = [
            "视频采集",
            "关键词搜索",
            "UP 主视频",
            "热搜搜索",
            "运行日志",
        ]

        for index, text in enumerate(nav_items):
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setFixedHeight(48)
            button.clicked.connect(
                lambda checked=False, page_index=index: self._switch_page(
                    page_index
                )
            )
            nav_group.addButton(button, index)
            self._nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        return sidebar

    def _make_metric_card(self, label, value, accent=False):
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setMinimumHeight(72)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setObjectName(
            "MetricValueAccent" if accent else "MetricValue"
        )
        layout.addWidget(value_widget)
        return card, value_widget

    def _switch_page(self, index):
        if not self._nav_buttons:
            return

        index = max(0, min(index, self.pages.count() - 1))
        self.pages.setCurrentIndex(index)
        self._nav_buttons[index].setChecked(True)
        self.page_title.setText(self._nav_buttons[index].text())

    def _toggle_sidebar(self):
        visible = self.sidebar.isVisible()
        self.sidebar.setVisible(not visible)

        if visible:
            self.sidebar_toggle.setText("›")
            self.sidebar_toggle.setToolTip("显示导航")
        else:
            self.sidebar_toggle.setText("‹")
            self.sidebar_toggle.setToolTip("隐藏导航")

    def _build_command_group(self):
        group = QGroupBox("执行计划")
        group.setMaximumHeight(270)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 18, 14, 12)
        layout.setSpacing(6)

        summary = QLabel("等待参数")
        summary.setObjectName("ExecutionSummary")
        summary.setWordWrap(True)
        summary.setMinimumHeight(68)
        layout.addWidget(summary)

        toggle = QToolButton()
        toggle.setObjectName("AdvancedToggle")
        toggle.setCheckable(True)
        toggle.setText("查看命令行")
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)

        preview = QPlainTextEdit()
        preview.setObjectName("CommandPreview")
        preview.setReadOnly(True)
        preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        preview.setMaximumHeight(82)
        preview.hide()

        font = QFont("Cascadia Mono")
        if not font.exactMatch():
            font = QFont("Consolas")
        font.setPointSize(9)
        preview.setFont(font)

        layout.addWidget(preview)

        def toggle_command(checked):
            preview.setVisible(checked)
            toggle.setText(
                "收起命令行" if checked else "查看命令行"
            )
            toggle.setArrowType(
                Qt.ArrowType.DownArrow
                if checked
                else Qt.ArrowType.RightArrow
            )

        toggle.toggled.connect(toggle_command)
        return group, summary, preview

    def _recent_output_entries(self, refresh=False):
        if self._recent_cache is not None and not refresh:
            return self._recent_cache

        output_dir = BASE_DIR / "output"
        entries = []

        if not output_dir.exists():
            self._recent_cache = entries
            return entries

        ignored = {"search", "playwright", "wireshark"}

        for path in output_dir.iterdir():
            if not path.is_dir() or path.name in ignored:
                continue

            try:
                modified_at = path.stat().st_mtime
            except OSError:
                continue

            video_name = self._friendly_video_output_name(path.name)
            file_entries = []

            for file_path in path.iterdir():
                if not file_path.is_file():
                    continue

                suffix = file_path.suffix.lower()

                if suffix not in {".csv", ".json"}:
                    continue

                try:
                    file_modified_at = file_path.stat().st_mtime
                except OSError:
                    continue

                file_entries.append(
                    (
                        file_modified_at,
                        file_path,
                        self._friendly_video_file_name(file_path, video_name),
                    )
                )

            if file_entries:
                for file_modified_at, file_path, display in file_entries:
                    entries.append(
                        {
                            "type": "视频",
                            "name": file_path.name,
                            "display": display,
                            "time": file_modified_at,
                            "path": file_path,
                        }
                    )
            else:
                entries.append(
                    {
                        "type": "视频",
                        "name": path.name,
                        "display": video_name,
                        "time": modified_at,
                        "path": path,
                    }
                )

        search_dir = output_dir / "search"

        if search_dir.exists():
            for path in search_dir.rglob("*.csv"):
                if not path.is_file():
                    continue

                try:
                    modified_at = path.stat().st_mtime
                except OSError:
                    continue

                entries.append(
                    {
                        "type": "搜索",
                        "name": path.stem,
                        "display": self._friendly_search_output_name(path),
                        "time": modified_at,
                        "path": path,
                    }
                )

        entries.sort(key=lambda item: item["time"], reverse=True)
        self._recent_cache = entries
        return self._recent_cache

    def _friendly_video_output_name(self, folder_name):
        parts = folder_name.rsplit("_", 1)

        if len(parts) != 2 or not parts[1].startswith("BV"):
            return folder_name

        base_name = parts[0]

        if "_" in base_name:
            up_name, title = base_name.split("_", 1)
            return f"{title} · {up_name}"

        return base_name

    def _friendly_video_file_name(self, path, video_name):
        filename = path.name

        if filename == "video_info.json":
            label = "视频概览"
        elif filename.startswith("comments_"):
            label = "评论"
        elif filename.startswith("danmaku_"):
            match = re.search(r"_p(\d+)\.csv$", filename)
            label = f"弹幕 P{match.group(1)}" if match else "弹幕"
        elif filename.startswith("subtitle_"):
            match = re.search(r"_p(\d+)_(.+)\.json$", filename)

            if match:
                label = f"字幕 P{match.group(1)} · {match.group(2)}"
            else:
                label = "字幕"
        else:
            label = path.stem

        return f"{label} · {video_name}"

    def _friendly_search_output_name(self, path):
        if path.name == "hot_list.csv":
            return "热搜汇总"

        keyword = path.parent.name
        count_text = ""
        parts = path.stem.rsplit("_", 1)

        if len(parts) == 2 and parts[1].isdigit():
            count_text = f" · {parts[1]} 条"

        if path.parent.parent.name == "up":
            return f"UP 视频 · {keyword}{count_text}"

        return f"{keyword}{count_text}"

    def _refresh_recent_outputs(self):
        entries = self._recent_output_entries(refresh=True)

        if hasattr(self, "metric_data_value"):
            self.metric_data_value.setText(f"{len(entries)}")

        self._refresh_project_data()

    def _build_project_data_panel(self, kind):
        titles = {
            "video": "当前视频数据",
            "search": "当前搜索数据",
            "user": "当前 UP 数据",
            "hot": "最近热搜数据",
        }
        group = QGroupBox(titles[kind])
        group.setObjectName("SideOutput")
        group.setFixedWidth(230)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 16, 14, 12)
        layout.setSpacing(9)
        layout.addStretch(1)

        count = QLabel("暂无数据")
        count.setObjectName("SideOutputCount")
        layout.addWidget(count)

        path = QLabel("等待采集")
        path.setObjectName("OutputPath")
        path.setWordWrap(True)
        layout.addWidget(path)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        open_button = QPushButton("打开目录")
        open_button.setEnabled(False)
        open_button.clicked.connect(
            lambda checked=False, panel_kind=kind: (
                self._open_project_directory(panel_kind)
            )
        )
        actions.addWidget(open_button)

        data_button = QPushButton("查看数据")
        data_button.setEnabled(False)
        data_button.clicked.connect(
            lambda checked=False, panel_kind=kind: (
                self._show_project_data(panel_kind)
            )
        )
        actions.addWidget(data_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        self._project_data_panels.append(
            {
                "kind": kind,
                "count": count,
                "path": path,
                "open_button": open_button,
                "data_button": data_button,
            }
        )
        return group

    def _current_project_path(self, kind):
        output_dir = BASE_DIR / "output"

        if kind == "video":
            bvid = self.bvid_edit.text().strip() or DEFAULT_BVID

            if not output_dir.exists():
                return None

            matches = [
                path
                for path in output_dir.iterdir()
                if path.is_dir() and path.name.endswith(f"_{bvid}")
            ]
            return self._newest_path(matches)

        if kind == "search":
            keyword = self.keyword_edit.text().strip()

            if not keyword:
                return None

            path = output_dir / "search" / keyword
            return path if path.exists() else None

        if kind == "user":
            mid = self.mid_edit.text().strip()

            if not mid:
                return None

            path = output_dir / "search" / "up" / mid
            return path if path.exists() else None

        hot_root = output_dir / "search" / "hot-search"

        if not hot_root.exists():
            return None

        runs = [path for path in hot_root.iterdir() if path.is_dir()]
        return self._newest_path(runs) or hot_root

    @staticmethod
    def _newest_path(paths):
        if not paths:
            return None

        return max(paths, key=lambda path: path.stat().st_mtime)

    @staticmethod
    def _count_project_files(path):
        try:
            return sum(
                1
                for item in path.rglob("*")
                if item.is_file()
                and item.suffix.lower() in {".csv", ".json"}
            )
        except OSError:
            return 0

    def _refresh_project_data(self):
        if not hasattr(self, "bvid_edit"):
            return

        for panel in self._project_data_panels:
            path = self._current_project_path(panel["kind"])
            has_path = path is not None and path.exists()
            file_count = self._count_project_files(path) if has_path else 0

            if file_count:
                panel["count"].setText(f"{file_count} 项数据")
            elif has_path:
                panel["count"].setText("暂无数据文件")
            else:
                panel["count"].setText("暂无数据")

            panel["path"].setText(path.name if has_path else "等待采集")
            panel["path"].setToolTip(str(path) if has_path else "")
            panel["open_button"].setEnabled(has_path)
            panel["data_button"].setEnabled(has_path)

    def _open_project_directory(self, kind):
        path = self._current_project_path(kind)

        if path is None or not path.exists():
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_project_data(self, kind):
        path = self._current_project_path(kind)

        if path is None or not path.exists():
            return

        DataBrowserDialog(self, initial_path=path).exec()

    @staticmethod
    def _make_task_grid(page):
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(14)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setRowStretch(2, 1)
        return layout

    @staticmethod
    def _add_task_sections(
        layout,
        parameter_group,
        command_group,
        project_data,
        start_button,
    ):
        layout.addWidget(parameter_group, 0, 0)
        layout.addWidget(project_data, 0, 1)
        layout.addWidget(command_group, 1, 0, 1, 2)
        layout.addWidget(
            start_button,
            3,
            0,
            1,
            2,
            Qt.AlignmentFlag.AlignRight,
        )

    def _build_video_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group = QGroupBox("采集参数")
        group.setMaximumWidth(660)
        form = QFormLayout(group)
        form.setContentsMargins(16, 20, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(18)

        self.bvid_edit = QLineEdit(DEFAULT_BVID)
        self.bvid_edit.setFixedWidth(300)
        self.bvid_edit.setPlaceholderText("BV...")
        form.addRow("视频编号", self.bvid_edit)

        self.video_action = QComboBox()
        self.video_action.setFixedWidth(300)
        self.video_action.addItem("视频概览", "info")
        self.video_action.addItem("评论", "comments")
        self.video_action.addItem("字幕", "subtitles")
        self.video_action.addItem("弹幕", "danmaku")
        self.video_action.addItem("全部采集", "all")
        self.video_action.setCurrentIndex(
            self.video_action.findData("all")
        )
        self.video_action.currentIndexChanged.connect(self._update_video_controls)
        self.video_action.currentIndexChanged.connect(
            self._update_video_preview
        )
        form.addRow("采集内容", self.video_action)

        self.video_page_edit = QLineEdit()
        self.video_page_edit.setFixedWidth(300)
        self.video_page_edit.setPlaceholderText("全部，或 1,3")
        self.video_page_edit.textChanged.connect(self._update_video_preview)
        form.addRow("分集范围", self.video_page_edit)

        self.subtitle_language_edit = QLineEdit()
        self.subtitle_language_edit.setFixedWidth(300)
        self.subtitle_language_edit.setPlaceholderText("例如 ai-zh、zh-CN")
        self.subtitle_language_edit.textChanged.connect(
            self._update_video_preview
        )
        self.bvid_edit.textChanged.connect(self._update_video_preview)
        self.bvid_edit.textChanged.connect(self._refresh_project_data)
        form.addRow("字幕语言", self.subtitle_language_edit)

        (
            command_group,
            self.video_execution_summary,
            self.video_command_preview,
        ) = self._build_command_group()

        self.video_start_button = self._make_start_button(
            "开始采集",
            self._start_video_task,
        )

        self._add_task_sections(
            layout,
            group,
            command_group,
            self._build_project_data_panel("video"),
            self.video_start_button,
        )

        self._update_video_preview()
        return page

    def _build_search_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group = QGroupBox("搜索参数")
        group.setMaximumWidth(660)
        form = QFormLayout(group)
        form.setContentsMargins(16, 20, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(18)

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setFixedWidth(320)
        self.keyword_edit.setPlaceholderText("输入搜索关键词")
        form.addRow("关键词", self.keyword_edit)

        self.search_page_edit = QLineEdit("1")
        self.search_page_edit.setFixedWidth(180)
        self.search_page_edit.setPlaceholderText("1 或 1,3")
        form.addRow("搜索页范围", self.search_page_edit)

        self.search_page_size = self._make_spin_box(1, 50, 20)
        self.search_page_size.setFixedWidth(130)
        form.addRow("每次读取", self.search_page_size)

        self.search_workers = self._make_spin_box(
            1,
            SEARCH_MAX_WORKERS,
            SEARCH_DEFAULT_WORKERS,
        )
        self.search_workers.setFixedWidth(130)
        self.search_workers.setToolTip(
            f"默认 {SEARCH_DEFAULT_WORKERS}，较高并发可能触发限制"
        )
        form.addRow("同时请求数", self.search_workers)

        self.keyword_edit.textChanged.connect(self._update_search_preview)
        self.keyword_edit.textChanged.connect(self._refresh_project_data)
        self.search_page_edit.textChanged.connect(self._update_search_preview)
        self.search_page_size.valueChanged.connect(self._update_search_preview)
        self.search_workers.valueChanged.connect(self._update_search_preview)

        (
            command_group,
            self.search_execution_summary,
            self.search_command_preview,
        ) = self._build_command_group()

        self.search_start_button = self._make_start_button(
            "开始搜索",
            self._start_search_task,
        )

        self._add_task_sections(
            layout,
            group,
            command_group,
            self._build_project_data_panel("search"),
            self.search_start_button,
        )

        self._update_search_preview()
        return page

    def _build_user_video_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group = QGroupBox("UP 主参数")
        group.setMaximumWidth(660)
        form = QFormLayout(group)
        form.setContentsMargins(16, 20, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(18)

        self.mid_edit = QLineEdit()
        self.mid_edit.setFixedWidth(220)
        self.mid_edit.setPlaceholderText("例如 267068018")
        form.addRow("UP 主 MID", self.mid_edit)

        self.user_page_size = self._make_spin_box(1, 50, 30)
        self.user_page_size.setFixedWidth(130)
        form.addRow("每次读取", self.user_page_size)

        self.user_workers = self._make_spin_box(
            1,
            SEARCH_MAX_WORKERS,
            SEARCH_DEFAULT_WORKERS,
        )
        self.user_workers.setFixedWidth(130)
        self.user_workers.setToolTip(
            f"默认 {SEARCH_DEFAULT_WORKERS}，较高并发可能触发限制"
        )
        form.addRow("同时请求数", self.user_workers)

        self.mid_edit.textChanged.connect(self._update_user_preview)
        self.mid_edit.textChanged.connect(self._refresh_project_data)
        self.user_page_size.valueChanged.connect(self._update_user_preview)
        self.user_workers.valueChanged.connect(self._update_user_preview)

        (
            command_group,
            self.user_execution_summary,
            self.user_command_preview,
        ) = self._build_command_group()

        self.user_start_button = self._make_start_button(
            "开始采集",
            self._start_user_video_task,
        )

        self._add_task_sections(
            layout,
            group,
            command_group,
            self._build_project_data_panel("user"),
            self.user_start_button,
        )

        self._update_user_preview()
        return page

    def _build_hot_search_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group = QGroupBox("热搜参数")
        group.setMaximumWidth(660)
        form = QFormLayout(group)
        form.setContentsMargins(16, 20, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(18)

        self.hot_limit = self._make_spin_box(1, 50, 10)
        self.hot_limit.setFixedWidth(130)
        form.addRow("热搜条数", self.hot_limit)

        self.hot_page_size = self._make_spin_box(1, 50, 20)
        self.hot_page_size.setFixedWidth(130)
        form.addRow("每次读取", self.hot_page_size)

        self.hot_workers = self._make_spin_box(
            1,
            SEARCH_MAX_WORKERS,
            SEARCH_DEFAULT_WORKERS,
        )
        self.hot_workers.setFixedWidth(130)
        self.hot_workers.setToolTip(
            f"默认 {SEARCH_DEFAULT_WORKERS}，较高并发可能触发限制"
        )
        form.addRow("同时请求数", self.hot_workers)

        self.hot_limit.valueChanged.connect(self._update_hot_preview)
        self.hot_page_size.valueChanged.connect(self._update_hot_preview)
        self.hot_workers.valueChanged.connect(self._update_hot_preview)

        (
            command_group,
            self.hot_execution_summary,
            self.hot_command_preview,
        ) = self._build_command_group()

        self.hot_start_button = self._make_start_button(
            "开始采集",
            self._start_hot_search_task,
        )

        self._add_task_sections(
            layout,
            group,
            command_group,
            self._build_project_data_panel("hot"),
            self.hot_start_button,
        )

        self._update_hot_preview()
        return page

    def _build_empty_log(self):
        frame = QFrame()
        frame.setObjectName("LogEmpty")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch(1)

        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_pixmap = self._load_rounded_pixmap(
            "empty_state.jpg",
            QSize(168, 168),
            8,
        )

        if not image_pixmap.isNull():
            image.setPixmap(image_pixmap)

        layout.addWidget(image, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("等待任务")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        caption = QLabel("任务启动后将在这里显示运行记录")
        caption.setObjectName("EmptyCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)
        layout.addStretch(1)
        return frame

    def _build_log_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.addStretch(1)

        clear_button = QPushButton("清空日志")
        clear_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        clear_button.clicked.connect(self._clear_log)
        toolbar.addWidget(clear_button)

        self.stop_button = QPushButton("停止任务")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        )
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_task)
        toolbar.addWidget(self.stop_button)
        layout.addLayout(toolbar)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Cascadia Mono")
        if not font.exactMatch():
            font = QFont("Consolas")
        font.setPointSize(10)
        self.log_edit.setFont(font)

        self.log_stack = QStackedWidget()
        self.log_empty = self._build_empty_log()
        self.log_stack.addWidget(self.log_empty)
        self.log_stack.addWidget(self.log_edit)
        self.log_stack.setCurrentWidget(self.log_empty)
        layout.addWidget(self.log_stack, 1)
        return page

    def _make_start_button(self, text, callback):
        button = QPushButton(text)
        button.setObjectName("PrimaryButton")
        button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        button.setIconSize(QSize(16, 16))
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.clicked.connect(callback)
        self._start_buttons.append(button)
        return button

    def _make_spin_box(self, minimum, maximum, value):
        spin_box = QSpinBox()
        spin_box.setLocale(QLocale.c())
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        return spin_box

    def _update_video_preview(self, *_):
        if not hasattr(self, "video_execution_summary"):
            return

        action = self.video_action.currentData()
        supports_page = action in {"subtitles", "danmaku"}
        supports_language = action == "subtitles"
        page_range = self.video_page_edit.text().strip()
        language = self.subtitle_language_edit.text().strip()
        bvid = self.bvid_edit.text().strip() or DEFAULT_BVID

        flags = {
            "info": "-i",
            "comments": "-c",
            "subtitles": "-s",
            "danmaku": "-d",
            "all": "-a",
        }
        command = ["main.py", flags[action], bvid]

        if supports_page and page_range:
            command.extend(["-p", page_range])

        if supports_language and language:
            command.extend(["--language", language])

        summary = [
            f"任务：{self.video_action.currentText()}",
            f"视频：{bvid}",
        ]

        if supports_page:
            summary.append(f"分集：{page_range or '全部'}")

        if supports_language:
            summary.append(f"字幕：{language or '全部语言'}")

        self.video_execution_summary.setText("\n".join(summary))
        self.video_command_preview.setPlainText(" ".join(command))

    def _update_search_preview(self, *_):
        if not hasattr(self, "search_execution_summary"):
            return

        keyword = self.keyword_edit.text().strip() or "未填写"
        page_range = self.search_page_edit.text().strip() or "1"
        command = ["main.py", "-k", f'"{keyword}"']

        if page_range != "1":
            command.extend(["-p", page_range])

        command.extend(
            [
                "--page-size",
                str(self.search_page_size.value()),
                "-w",
                str(self.search_workers.value()),
            ]
        )
        self.search_execution_summary.setText(
            "\n".join(
                [
                    "任务：关键词搜索",
                    f"关键词：{keyword}",
                    f"页码：{page_range}",
                    (
                        f"读取：每次 {self.search_page_size.value()} 条 · "
                        f"同时 {self.search_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.search_command_preview.setPlainText(" ".join(command))

    def _update_user_preview(self, *_):
        if not hasattr(self, "user_execution_summary"):
            return

        mid = self.mid_edit.text().strip() or "未填写"
        command = [
            "main.py",
            "--mid",
            mid,
            "--page-size",
            str(self.user_page_size.value()),
            "-w",
            str(self.user_workers.value()),
        ]
        self.user_execution_summary.setText(
            "\n".join(
                [
                    "任务：UP 主全部视频",
                    f"UP 主 MID：{mid}",
                    (
                        f"读取：每次 {self.user_page_size.value()} 条 · "
                        f"同时 {self.user_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.user_command_preview.setPlainText(" ".join(command))

    def _update_hot_preview(self, *_):
        if not hasattr(self, "hot_execution_summary"):
            return

        command = [
            "main.py",
            "-H",
            "--limit",
            str(self.hot_limit.value()),
            "--page-size",
            str(self.hot_page_size.value()),
            "-w",
            str(self.hot_workers.value()),
        ]
        self.hot_execution_summary.setText(
            "\n".join(
                [
                    "任务：热搜搜索",
                    f"热搜：前 {self.hot_limit.value()} 条",
                    (
                        f"读取：每次 {self.hot_page_size.value()} 条 · "
                        f"同时 {self.hot_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.hot_command_preview.setPlainText(" ".join(command))

    def _apply_style(self):
        self.setStyleSheet(APP_STYLE)

    def _update_video_controls(self):
        action = self.video_action.currentData()
        supports_page = action in {"subtitles", "danmaku"}
        supports_language = action == "subtitles"

        self.video_page_edit.setEnabled(supports_page)
        self.subtitle_language_edit.setEnabled(supports_language)

    def _check_login(self):
        self._start_task(["-l"], "检查登录")

    def _start_video_task(self):
        bvid = self.bvid_edit.text().strip() or DEFAULT_BVID

        if not BVID_PATTERN.fullmatch(bvid):
            self._show_input_error("视频编号格式不正确。")
            return

        action = self.video_action.currentData()
        action_flags = {
            "info": "-i",
            "comments": "-c",
            "subtitles": "-s",
            "danmaku": "-d",
            "all": "-a",
        }
        args = [action_flags[action], bvid]

        if action in {"subtitles", "danmaku"}:
            page_range = self._read_page_range(self.video_page_edit.text())

            if page_range is None:
                return

            if page_range:
                args.extend(["-p", page_range])

        if action == "subtitles":
            language = self.subtitle_language_edit.text().strip()

            if language:
                args.extend(["--language", language])

        self._start_task(args, f"视频采集：{self.video_action.currentText()}")

    def _start_search_task(self):
        keyword = self.keyword_edit.text().strip()

        if not keyword:
            self._show_input_error("请输入搜索关键词。")
            self.keyword_edit.setFocus()
            return

        page_range = self._read_page_range(self.search_page_edit.text())

        if page_range is None:
            return

        args = ["-k", keyword]

        if page_range:
            args.extend(["-p", page_range])

        args.extend(
            [
                "--page-size",
                str(self.search_page_size.value()),
                "-w",
                str(self.search_workers.value()),
            ]
        )
        self._start_task(args, f"关键词搜索：{keyword}")

    def _start_user_video_task(self):
        mid = self.mid_edit.text().strip()

        if not mid.isdigit() or int(mid) <= 0:
            self._show_input_error("UP 主 MID 必须是大于 0 的数字。")
            self.mid_edit.setFocus()
            return

        args = [
            "--mid",
            mid,
            "--page-size",
            str(self.user_page_size.value()),
            "-w",
            str(self.user_workers.value()),
        ]
        self._start_task(args, f"UP 主视频：{mid}")

    def _start_hot_search_task(self):
        args = [
            "-H",
            "--limit",
            str(self.hot_limit.value()),
            "--page-size",
            str(self.hot_page_size.value()),
            "-w",
            str(self.hot_workers.value()),
        ]
        self._start_task(args, "热搜搜索")

    def _read_page_range(self, value):
        value = value.strip()

        if not value:
            return ""

        try:
            start, end = parse_page_range(value)
        except Exception:
            self._show_input_error(
                "页范围格式不正确，应填写 1 或 1,3。"
            )
            return None

        return str(start) if start == end else f"{start},{end}"

    def _start_task(self, args, title):
        if self._busy:
            return

        active_page = self.pages.currentIndex()
        self._task_title = title
        self._task_page = active_page
        self._log_header(title, args)
        self._set_busy(True, "运行中")
        self.pages.setCurrentIndex(active_page)
        self._nav_buttons[active_page].setChecked(True)
        self._login_prompt_seen = False
        self._scan_buffer = ""

        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments([str(BASE_DIR / "main.py"), *args])
        process.setWorkingDirectory(str(BASE_DIR))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(environment)

        process.readyReadStandardOutput.connect(self._read_process_output)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)

        self._process = process
        process.start()

        if not process.waitForStarted(3000):
            self._append_log("无法启动 Python 进程。\n")
            self._set_busy(False, "启动失败")

    def _read_process_output(self):
        if self._process is None:
            return

        output = self._process.readAllStandardOutput().toStdString()
        output = output.replace("\r\n", "\n").replace("\r", "\n")
        self._append_log(output)
        self._scan_buffer = (self._scan_buffer + output)[-1000:]

        if "检测到有效登录状态" in output:
            self.metric_login_value.setText("已连接")
        elif "请在浏览器中手动登录" in output:
            self.metric_login_value.setText("等待登录")
        elif "登录状态已经保存" in output:
            self.metric_login_value.setText("已登录")

        if LOGIN_PROMPT in self._scan_buffer and not self._login_prompt_seen:
            self._login_prompt_seen = True
            QTimer.singleShot(0, self._show_login_dialog)

    def _show_login_dialog(self):
        if self._process is None:
            return

        QMessageBox.information(
            self,
            "需要登录",
            "请在 Chrome 中完成 Bilibili 登录，然后点击“确定”。",
        )

        if self._process is not None:
            self._process.write(b"\n")

    def _process_finished(self, exit_code, exit_status):
        success = (
            exit_status == QProcess.ExitStatus.NormalExit
            and exit_code == 0
        )

        if success:
            self._append_log("\n任务完成。\n")
            self._refresh_recent_outputs()
            self._set_busy(False, "已完成")
            self.statusBar().showMessage("任务完成", 5000)
            project_kind = {
                0: "video",
                1: "search",
                2: "user",
                3: "hot",
            }.get(self._task_page)
            project_path = (
                self._current_project_path(project_kind)
                if project_kind
                else None
            )
            CompletionDialog(
                self._task_title or "任务",
                path=project_path,
                parent=self,
            ).exec()
        else:
            self._append_log(f"\n任务结束，退出码：{exit_code}。\n")
            self._set_busy(False, "失败")
            self.statusBar().showMessage("任务失败，请查看运行日志", 8000)

        self._process = None

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._append_log("\nPython 进程启动失败。\n")
            self._set_busy(False, "启动失败")

    def _stop_task(self):
        if self._process is None:
            return

        answer = QMessageBox.question(
            self,
            "停止任务",
            "确定要停止当前任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self._append_log("\n正在停止任务...\n")
        self._process.terminate()
        QTimer.singleShot(3000, self._kill_process_if_running)

    def _kill_process_if_running(self):
        if self._process is not None:
            self._process.kill()

    def _set_busy(self, busy, status):
        self._busy = busy
        self.metric_status_value.setText(status)
        self.login_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

        for button in self._start_buttons:
            button.setEnabled(not busy)

        if busy:
            self.progress.show()
            self._refresh_timer.start()
        else:
            self.progress.hide()
            self._refresh_timer.stop()

    def _append_log(self, text):
        if text and hasattr(self, "log_stack"):
            self.log_stack.setCurrentWidget(self.log_edit)

        cursor = self.log_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.log_edit.setTextCursor(cursor)
        self.log_edit.ensureCursorVisible()

    def _log_header(self, title, args):
        separator = "\n" if self.log_edit.toPlainText() else ""
        command = " ".join([str(BASE_DIR / "main.py"), *args])
        self._append_log(
            f"{separator}[{title}]\n$ {sys.executable} {command}\n"
        )

    def _clear_log(self):
        self.log_edit.clear()

        if hasattr(self, "log_stack"):
            self.log_stack.setCurrentWidget(self.log_empty)

    def _open_output_dir(self):
        output_dir = BASE_DIR / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        self._refresh_recent_outputs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))

    def _show_input_error(self, message):
        QMessageBox.warning(self, "参数错误", message)

    def closeEvent(self, event):
        if self._busy:
            answer = QMessageBox.question(
                self,
                "任务运行中",
                "任务仍在运行，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.No:
                event.ignore()
                return

            if self._process is not None:
                self._process.kill()

        event.accept()
