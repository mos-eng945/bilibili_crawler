"""Main Qt window and crawler process control."""

import re
import sys

from PySide6.QtCore import (
    QLocale,
    QProcess,
    QProcessEnvironment,
    QRectF,
    QSettings,
    QSize,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crawler_common import SEARCH_DEFAULT_WORKERS, SEARCH_MAX_WORKERS
from config import (
    BASE_DIR,
    DEFAULT_BVID,
    parse_page_range,
)
from output_paths import (
    OUTPUT_DIR,
    find_user_dir,
    hot_project_dir,
    latest_search_keyword,
    latest_user_mid,
    search_project_dir,
    video_project_dir,
)
from qt_ui.dialogs import CompletionDialog, DataBrowserDialog
from qt_ui.formatting import friendly_video_name
from qt_ui.theme import APP_STYLE, icon

BVID_PATTERN = re.compile(r"^BV[0-9A-Za-z]+$")
LOGIN_PROMPT = "登录完成后按回车"
SETTINGS_ORGANIZATION = "BilibiliDataCrawler"
SETTINGS_APPLICATION = "BilibiliDataCrawler"
VIDEO_ACTION_FLAGS = {
    "info": "-i",
    "comments": "-c",
    "subtitles": "-s",
    "danmaku": "-d",
    "all": "-a",
}


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
        self._task_has_output = False
        self._start_buttons = []
        self._nav_buttons = []
        self._project_data_panels = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._refresh_project_data)

        # 输入框每敲一个字都会 textChanged；这里合并成一次，避免逐键遍历磁盘
        self._project_refresh_timer = QTimer(self)
        self._project_refresh_timer.setSingleShot(True)
        self._project_refresh_timer.setInterval(200)
        self._project_refresh_timer.timeout.connect(
            self._refresh_project_data
        )

        self.setWindowTitle("Bilibili 数据采集器")
        self.setWindowIcon(self._app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(1060, 740)

        self._build_ui()
        self._apply_style()
        self._update_video_controls()
        self._restore_settings()
        self._refresh_project_data()

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
        self.metric_strip.addWidget(status_card)
        self.metric_strip.addWidget(login_card)
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
        self._refresh_project_data()

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
        self.login_button.setIcon(icon("icon-check.svg"))
        self.login_button.clicked.connect(self._check_login)
        layout.addWidget(self.login_button)

        return header

    def _build_sidebar_rail(self):
        rail = QWidget()
        rail.setObjectName("SidebarRail")
        rail.setFixedWidth(26)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        self.sidebar_toggle = QPushButton()
        self.sidebar_toggle.setObjectName("RailButton")
        self.sidebar_toggle.setFixedSize(26, 46)
        self.sidebar_toggle.setIcon(icon("icon-chevron-left.svg"))
        self.sidebar_toggle.setIconSize(QSize(12, 12))
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.setToolTip("收起导航")
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
            if text == "运行日志":
                # 「打开目录」是动作不是页面，放在日志页上面
                open_dir_button = QPushButton("打开目录")
                open_dir_button.setObjectName("NavButton")
                open_dir_button.setFixedHeight(48)
                open_dir_button.setToolTip("用资源管理器打开 output 目录")
                open_dir_button.clicked.connect(self._open_output_dir)
                layout.addWidget(open_dir_button)

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
            self.sidebar_toggle.setIcon(icon("icon-chevron-right.svg"))
            self.sidebar_toggle.setToolTip("展开导航")
        else:
            self.sidebar_toggle.setIcon(icon("icon-chevron-left.svg"))
            self.sidebar_toggle.setToolTip("收起导航")

    def _build_command_group(self):
        group = QGroupBox("执行计划")
        group.setMaximumHeight(270)

        layout = QVBoxLayout(group)
        # 与其它分组框保持同一内容左边距
        layout.setContentsMargins(16, 18, 16, 0)
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

        preview.setFont(self._mono_font(9))

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
        # 横向/顶部与左侧参数框对齐，底部不叠加，避免多出一块空白
        layout.setContentsMargins(16, 16, 16, 0)
        layout.setSpacing(8)

        count = QLabel("暂无数据")
        count.setObjectName("SideOutputCount")
        layout.addWidget(count)

        path = QLabel("等待采集")
        path.setObjectName("OutputPath")
        path.setWordWrap(False)
        layout.addWidget(path)

        data_button = QPushButton("查看数据")
        data_button.setEnabled(False)
        data_button.clicked.connect(
            lambda checked=False, panel_kind=kind: (
                self._show_project_data(panel_kind)
            )
        )
        layout.addWidget(data_button)
        layout.addStretch(1)

        self._project_data_panels.append(
            {
                "kind": kind,
                "count": count,
                "path": path,
                "data_button": data_button,
            }
        )
        return group

    def _current_project_path(self, kind):
        if kind == "video":
            bvid = self.bvid_edit.text().strip() or DEFAULT_BVID
            return video_project_dir(bvid)

        if kind == "search":
            return search_project_dir(self.keyword_edit.text().strip())

        if kind == "user":
            return find_user_dir(self.mid_edit.text().strip())

        return hot_project_dir()

    def _settings(self):
        return QSettings(
            SETTINGS_ORGANIZATION,
            SETTINGS_APPLICATION,
        )

    @staticmethod
    def _int_setting(settings, key, default):
        """读取整数配置，兼容 QSettings.value 返回 object 的类型签名。"""
        value = settings.value(key, default, type=int)

        if isinstance(value, (int, float)):
            return int(value)

        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    def _restore_settings(self):
        settings = self._settings()

        bvid = str(
            settings.value("video/bvid", DEFAULT_BVID)
        ).strip()
        self.bvid_edit.setText(bvid or DEFAULT_BVID)

        action = str(settings.value("video/action", "all"))
        action_index = self.video_action.findData(action)

        if action_index >= 0:
            self.video_action.setCurrentIndex(action_index)

        self.video_page_edit.setText(
            str(settings.value("video/page_range", ""))
        )
        self.subtitle_language_edit.setText(
            str(settings.value("video/language", ""))
        )
        comment_mode = self._int_setting(settings, "video/comment_mode", 2)
        comment_mode_index = self.comment_mode.findData(comment_mode)

        if comment_mode_index >= 0:
            self.comment_mode.setCurrentIndex(comment_mode_index)

        self.comment_page_size.setValue(
            self._int_setting(settings, "video/comment_page_size", 30)
        )

        keyword = str(
            settings.value("search/keyword", "")
        ).strip()

        if search_project_dir(keyword) is None:
            keyword = latest_search_keyword()

        if keyword:
            self.keyword_edit.setText(keyword)

        self.search_page_edit.setText(
            str(settings.value("search/page_range", "1")) or "1"
        )
        self.search_page_size.setValue(
            self._int_setting(settings, "search/page_size", 20)
        )
        self.search_workers.setValue(
            self._int_setting(
                settings, "search/workers", SEARCH_DEFAULT_WORKERS
            )
        )

        mid = str(settings.value("user/mid", "")).strip()

        if find_user_dir(mid) is None:
            mid = latest_user_mid()

        if mid:
            self.mid_edit.setText(mid)

        self.user_page_size.setValue(
            self._int_setting(settings, "user/page_size", 30)
        )
        self.user_workers.setValue(
            self._int_setting(
                settings, "user/workers", SEARCH_DEFAULT_WORKERS
            )
        )

        self.hot_limit.setValue(
            self._int_setting(settings, "hot/limit", 10)
        )
        self.hot_page_size.setValue(
            self._int_setting(settings, "hot/page_size", 20)
        )
        self.hot_workers.setValue(
            self._int_setting(
                settings, "hot/workers", SEARCH_DEFAULT_WORKERS
            )
        )

        page_index = self._int_setting(settings, "window/page", 0)
        self._switch_page(page_index)
        self._refresh_project_data()

    def _save_settings(self):
        settings = self._settings()
        settings.setValue("video/bvid", self.bvid_edit.text().strip())
        settings.setValue(
            "video/action",
            self.video_action.currentData(),
        )
        settings.setValue(
            "video/page_range",
            self.video_page_edit.text().strip(),
        )
        settings.setValue(
            "video/language",
            self.subtitle_language_edit.text().strip(),
        )
        settings.setValue(
            "video/comment_mode",
            self.comment_mode.currentData(),
        )
        settings.setValue(
            "video/comment_page_size",
            self.comment_page_size.value(),
        )
        settings.setValue(
            "search/keyword",
            self.keyword_edit.text().strip(),
        )
        settings.setValue(
            "search/page_range",
            self.search_page_edit.text().strip(),
        )
        settings.setValue(
            "search/page_size",
            self.search_page_size.value(),
        )
        settings.setValue(
            "search/workers",
            self.search_workers.value(),
        )
        settings.setValue("user/mid", self.mid_edit.text().strip())
        settings.setValue(
            "user/page_size",
            self.user_page_size.value(),
        )
        settings.setValue(
            "user/workers",
            self.user_workers.value(),
        )
        settings.setValue("hot/limit", self.hot_limit.value())
        settings.setValue(
            "hot/page_size",
            self.hot_page_size.value(),
        )
        settings.setValue(
            "hot/workers",
            self.hot_workers.value(),
        )
        settings.setValue("window/page", self.pages.currentIndex())
        settings.sync()

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

    def _schedule_project_refresh(self, *_):
        """输入变化时合并刷新，避免每敲一个字都去遍历 output 目录。"""
        self._project_refresh_timer.start(200)

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

            if not has_path:
                display_name = "等待采集"
            elif panel["kind"] == "video":
                # 文件夹名是 UP名_标题_BV号，太长；显示成「标题 · UP名」
                display_name = friendly_video_name(path.name)
            else:
                display_name = path.name

            # 面板固定 230px，路径框只留一行，长了用省略号，完整值放 tooltip
            metrics = QFontMetrics(panel["path"].font())
            panel["path"].setText(
                metrics.elidedText(
                    display_name,
                    Qt.TextElideMode.ElideRight,
                    180,
                )
            )
            panel["path"].setToolTip(str(path) if has_path else "")
            panel["data_button"].setEnabled(has_path)

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
        # 参数框占弹性宽度，数据面板固定宽度贴右，第一行铺满整宽
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        # 参数卡片吸收多余高度，内容把整页填满，底部不留空
        layout.setRowStretch(0, 1)
        layout.setRowStretch(2, 0)
        return layout

    @staticmethod
    def _add_task_sections(
        layout,
        parameter_group,
        command_group,
        project_data,
        start_button,
    ):
        # 参数卡片占满整行；下面一行左边执行计划、右边数据面板
        layout.addWidget(parameter_group, 0, 0, 1, 2)
        layout.addWidget(command_group, 1, 0)
        layout.addWidget(
            project_data,
            1,
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(
            start_button,
            3,
            0,
            1,
            2,
            Qt.AlignmentFlag.AlignRight,
        )

    def _assemble_task_tab(
        self,
        layout,
        parameter_group,
        kind,
        start_text,
        start_callback,
    ):
        (
            command_group,
            execution_summary,
            command_preview,
        ) = self._build_command_group()
        start_button = self._make_start_button(start_text, start_callback)
        self._add_task_sections(
            layout,
            parameter_group,
            command_group,
            self._build_project_data_panel(kind),
            start_button,
        )
        return execution_summary, command_preview

    @staticmethod
    def _make_parameter_group(title, columns=2):
        """参数区用多列网格：一行放 `columns` 组「标签 + 控件」。"""
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setContentsMargins(16, 16, 16, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        for column in range(columns):
            grid.setColumnStretch(column * 2 + 1, 1)

        return group, grid

    @staticmethod
    def _add_param(grid, row, column, text, field, span=1):
        """把一组「标签 + 控件」放进网格，`span` 表示占几列。"""
        label = QLabel(text)
        grid.addWidget(label, row, column * 2)
        grid.addWidget(
            field,
            row,
            column * 2 + 1,
            1,
            span * 2 - 1,
        )
        return label

    @staticmethod
    def _balance_parameter_rows(grid):
        """让每个「可见行」均分卡片高度，行距才不会忽大忽小。"""
        for row in range(grid.rowCount()):
            has_visible = any(
                grid.itemAtPosition(row, column) is not None
                and grid.itemAtPosition(row, column).widget() is not None
                and grid.itemAtPosition(row, column).widget().isVisible()
                for column in range(grid.columnCount())
            )
            grid.setRowStretch(row, 1 if has_visible else 0)

    def _build_video_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group, grid = self._make_parameter_group("采集参数", columns=1)
        self.video_grid = grid
        self.video_labels = {}

        self.bvid_edit = QLineEdit(DEFAULT_BVID)
        self.bvid_edit.setMinimumWidth(160)
        self.bvid_edit.setPlaceholderText("BV...")
        self._add_param(grid, 0, 0, "视频编号", self.bvid_edit)

        self.video_action = QComboBox()
        self.video_action.setMinimumWidth(160)
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
        self._add_param(grid, 1, 0, "采集内容", self.video_action)

        self.comment_options = QWidget()
        # 这一行是可纵向拉伸的容器，若不锁住会把卡片余高全吃掉、行距不均
        self.comment_options.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        comment_options_layout = QHBoxLayout(self.comment_options)
        comment_options_layout.setContentsMargins(0, 0, 0, 0)
        comment_options_layout.setSpacing(8)

        self.comment_mode = QComboBox()
        self.comment_mode.setFixedWidth(190)
        self.comment_mode.addItem("时间顺序", 2)
        self.comment_mode.addItem("热门评论", 3)
        self.comment_mode.currentIndexChanged.connect(
            self._update_video_preview
        )
        comment_options_layout.addWidget(self.comment_mode)

        self.comment_page_size = self._make_spin_box(1, 30, 30)
        self.comment_page_size.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.comment_page_size.setSuffix(" 条")
        self.comment_page_size.setObjectName("CompactSpin")
        self.comment_page_size.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        # 96px 时聚焦编辑会把数字挤出可视区，只剩后缀「条」
        self.comment_page_size.setFixedWidth(112)
        self.comment_page_size.setToolTip("输入 1-30")
        self.comment_page_size.valueChanged.connect(
            self._update_video_preview
        )
        comment_options_layout.addWidget(QLabel("每页"))
        comment_options_layout.addWidget(self.comment_page_size)
        comment_options_layout.addStretch(1)
        self.video_labels[self.comment_options] = self._add_param(
            grid, 2, 0, "评论设置", self.comment_options
        )

        self.video_page_edit = QLineEdit()
        self.video_page_edit.setMinimumWidth(160)
        self.video_page_edit.setPlaceholderText("全部，或 1,3")
        self.video_page_edit.textChanged.connect(self._update_video_preview)
        self.video_labels[self.video_page_edit] = self._add_param(
            grid, 3, 0, "分集范围", self.video_page_edit
        )

        self.subtitle_language_edit = QLineEdit()
        self.subtitle_language_edit.setMinimumWidth(160)
        self.subtitle_language_edit.setPlaceholderText("例如 ai-zh、zh-CN")
        self.subtitle_language_edit.textChanged.connect(
            self._update_video_preview
        )
        self.bvid_edit.textChanged.connect(self._update_video_preview)
        self.bvid_edit.textChanged.connect(
            self._schedule_project_refresh
        )
        self.video_labels[self.subtitle_language_edit] = self._add_param(
            grid, 4, 0, "字幕语言", self.subtitle_language_edit
        )

        (
            self.video_execution_summary,
            self.video_command_preview,
        ) = self._assemble_task_tab(
            layout,
            group,
            "video",
            "开始采集",
            self._start_video_task,
        )
        self._balance_parameter_rows(grid)
        self._update_video_preview()
        return page

    def _build_search_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group, grid = self._make_parameter_group("搜索参数", columns=1)

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setMinimumWidth(160)
        self.keyword_edit.setPlaceholderText("输入搜索关键词")
        self._add_param(grid, 0, 0, "关键词", self.keyword_edit)

        self.search_page_edit = QLineEdit("1")
        self.search_page_edit.setMinimumWidth(120)
        self.search_page_edit.setPlaceholderText("10 表示 1-10；或 1,3")
        self._add_param(grid, 1, 0, "搜索页范围", self.search_page_edit)

        self.search_page_size = self._make_spin_box(1, 50, 20)
        self._add_param(grid, 2, 0, "每次读取", self.search_page_size)

        self.search_workers = self._make_worker_spin(
            f"默认 {SEARCH_DEFAULT_WORKERS}，较高并发可能触发限制",
            width=None,
        )
        self._add_param(grid, 3, 0, "同时请求数", self.search_workers)

        self.keyword_edit.textChanged.connect(self._update_search_preview)
        self.keyword_edit.textChanged.connect(
            self._schedule_project_refresh
        )
        self.search_page_edit.textChanged.connect(self._update_search_preview)
        self.search_page_size.valueChanged.connect(self._update_search_preview)
        self.search_workers.valueChanged.connect(self._update_search_preview)

        (
            self.search_execution_summary,
            self.search_command_preview,
        ) = self._assemble_task_tab(
            layout,
            group,
            "search",
            "开始搜索",
            self._start_search_task,
        )
        self._balance_parameter_rows(grid)
        self._update_search_preview()
        return page

    def _build_user_video_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group, grid = self._make_parameter_group("UP 主参数", columns=1)

        self.mid_edit = QLineEdit()
        self.mid_edit.setMinimumWidth(140)
        self.mid_edit.setPlaceholderText("例如 267068018")
        self._add_param(grid, 0, 0, "UP 主 MID", self.mid_edit)

        self.user_page_size = self._make_spin_box(1, 50, 30)
        self._add_param(grid, 1, 0, "每次读取", self.user_page_size)

        self.user_workers = self._make_worker_spin(
            f"默认 {SEARCH_DEFAULT_WORKERS}，较高并发可能触发限制",
            width=None,
        )
        self._add_param(grid, 2, 0, "同时请求数", self.user_workers)

        self.mid_edit.textChanged.connect(self._update_user_preview)
        self.mid_edit.textChanged.connect(
            self._schedule_project_refresh
        )
        self.user_page_size.valueChanged.connect(self._update_user_preview)
        self.user_workers.valueChanged.connect(self._update_user_preview)

        (
            self.user_execution_summary,
            self.user_command_preview,
        ) = self._assemble_task_tab(
            layout,
            group,
            "user",
            "开始采集",
            self._start_user_video_task,
        )
        self._balance_parameter_rows(grid)
        self._update_user_preview()
        return page

    def _build_hot_search_tab(self):
        page = QWidget()
        layout = self._make_task_grid(page)

        group, grid = self._make_parameter_group("热搜参数", columns=1)

        self.hot_limit = self._make_spin_box(1, 50, 10)
        self._add_param(grid, 0, 0, "热搜条数", self.hot_limit)

        self.hot_page_size = self._make_spin_box(1, 50, 20)
        self._add_param(grid, 1, 0, "每次读取", self.hot_page_size)

        self.hot_workers = self._make_worker_spin(
            f"默认 {SEARCH_DEFAULT_WORKERS}，单个热搜词内部的请求并发数",
            width=None,
        )
        self._add_param(grid, 2, 0, "关键词并发数", self.hot_workers)

        self.hot_limit.valueChanged.connect(self._update_hot_preview)
        self.hot_page_size.valueChanged.connect(self._update_hot_preview)
        self.hot_workers.valueChanged.connect(self._update_hot_preview)

        (
            self.hot_execution_summary,
            self.hot_command_preview,
        ) = self._assemble_task_tab(
            layout,
            group,
            "hot",
            "开始采集",
            self._start_hot_search_task,
        )
        self._balance_parameter_rows(grid)
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
            QSize(112, 112),
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
        clear_button.setIcon(icon("icon-trash.svg"))
        clear_button.clicked.connect(self._clear_log)
        toolbar.addWidget(clear_button)

        self.stop_button = QPushButton("停止任务")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setIcon(icon("icon-stop.svg"))
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_task)
        toolbar.addWidget(self.stop_button)
        layout.addLayout(toolbar)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_edit.setFont(self._mono_font(10))

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
        button.setIcon(icon("icon-play.svg"))
        button.setIconSize(QSize(16, 16))
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.clicked.connect(callback)
        self._start_buttons.append(button)
        return button

    def _make_spin_box(self, minimum, maximum, value, width=None):
        spin_box = QSpinBox()
        spin_box.setLocale(QLocale.c())
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)

        if width is not None:
            spin_box.setFixedWidth(width)

        return spin_box

    def _make_worker_spin(self, tooltip, width=130):
        spin_box = self._make_spin_box(
            1,
            SEARCH_MAX_WORKERS,
            SEARCH_DEFAULT_WORKERS,
            width=width,
        )
        spin_box.setToolTip(tooltip)
        return spin_box

    @staticmethod
    def _mono_font(point_size):
        font = QFont("Cascadia Mono")

        if not font.exactMatch():
            font = QFont("Consolas")

        font.setPointSize(point_size)
        return font

    def _video_args(self, page_range):
        action = self.video_action.currentData()
        bvid = self.bvid_edit.text().strip() or DEFAULT_BVID
        args = [VIDEO_ACTION_FLAGS[action], bvid]

        if action in {"subtitles", "danmaku"} and page_range:
            args.extend(["-p", page_range])

        if action == "subtitles":
            language = self.subtitle_language_edit.text().strip()

            if language:
                args.extend(["--language", language])

        if action in {"comments", "all"}:
            args.extend(
                [
                    "--comment-mode",
                    (
                        "hot"
                        if self.comment_mode.currentData() == 3
                        else "time"
                    ),
                    "--comment-page-size",
                    str(self.comment_page_size.value()),
                ]
            )

        return args

    def _search_args(self, page_range):
        args = ["-k", self.keyword_edit.text().strip() or "<未填写>"]

        if page_range:
            args.extend(["--search-page", page_range])

        args.extend(
            [
                "--page-size",
                str(self.search_page_size.value()),
                "-w",
                str(self.search_workers.value()),
            ]
        )
        return args

    def _user_args(self):
        return [
            "--mid",
            self.mid_edit.text().strip() or "<未填写>",
            "--page-size",
            str(self.user_page_size.value()),
            "-w",
            str(self.user_workers.value()),
        ]

    def _hot_args(self):
        return [
            "-H",
            "--limit",
            str(self.hot_limit.value()),
            "--page-size",
            str(self.hot_page_size.value()),
            "-w",
            str(self.hot_workers.value()),
        ]

    @staticmethod
    def _preview_command(args):
        return " ".join(
            f'"{arg}"' if " " in str(arg) else str(arg)
            for arg in args
        )

    def _update_video_preview(self, *_):
        if not hasattr(self, "video_execution_summary"):
            return

        action = self.video_action.currentData()
        supports_page = action in {"subtitles", "danmaku"}
        supports_language = action == "subtitles"
        supports_comments = action in {"comments", "all"}
        page_range = (
            self._normalize_page_range(self.video_page_edit.text()) or ""
        )
        language = self.subtitle_language_edit.text().strip()
        bvid = self.bvid_edit.text().strip() or DEFAULT_BVID

        summary = [
            f"任务：{self.video_action.currentText()}",
            f"视频：{bvid}",
        ]

        if supports_page:
            summary.append(f"分集：{page_range or '全部'}")

        if supports_language:
            summary.append(f"字幕：{language or '全部语言'}")

        if supports_comments:
            summary.append(
                f"评论：{self.comment_mode.currentText()} · "
                f"每页 {self.comment_page_size.value()} 条"
            )

        self.video_execution_summary.setText("\n".join(summary))
        self.video_command_preview.setPlainText(
            self._preview_command(["main.py", *self._video_args(page_range)])
        )

    def _update_search_preview(self, *_):
        if not hasattr(self, "search_execution_summary"):
            return

        keyword = self.keyword_edit.text().strip() or "未填写"
        page_range = (
            self._normalize_page_range(self.search_page_edit.text()) or ""
        )
        display_page_range = page_range or "1"

        if page_range.isdigit() and int(page_range) > 1:
            display_page_range = f"1-{page_range}"

        self.search_execution_summary.setText(
            "\n".join(
                [
                    "任务：关键词搜索",
                    f"关键词：{keyword}",
                    f"页码：{display_page_range}",
                    (
                        f"读取：每次 {self.search_page_size.value()} 条 · "
                        f"同时 {self.search_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.search_command_preview.setPlainText(
            self._preview_command(["main.py", *self._search_args(page_range)])
        )

    def _update_user_preview(self, *_):
        if not hasattr(self, "user_execution_summary"):
            return

        self.user_execution_summary.setText(
            "\n".join(
                [
                    "任务：UP 主全部视频",
                    f"UP 主 MID：{self.mid_edit.text().strip() or '未填写'}",
                    (
                        f"读取：每次 {self.user_page_size.value()} 条 · "
                        f"同时 {self.user_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.user_command_preview.setPlainText(
            self._preview_command(["main.py", *self._user_args()])
        )

    def _update_hot_preview(self, *_):
        if not hasattr(self, "hot_execution_summary"):
            return

        self.hot_execution_summary.setText(
            "\n".join(
                [
                    "任务：热搜搜索",
                    f"热搜：前 {self.hot_limit.value()} 条",
                    (
                        f"读取：每次 {self.hot_page_size.value()} 条 · "
                        f"关键词内部 {self.hot_workers.value()} 个请求"
                    ),
                ]
            )
        )
        self.hot_command_preview.setPlainText(
            self._preview_command(["main.py", *self._hot_args()])
        )

    def _apply_style(self):
        self.setStyleSheet(APP_STYLE)

    def _update_video_controls(self):
        action = self.video_action.currentData()
        supports_page = action in {"subtitles", "danmaku"}
        supports_language = action == "subtitles"
        supports_comments = action in {"comments", "all"}

        rows = (
            (self.comment_options, supports_comments),
            (self.video_page_edit, supports_page),
            (self.subtitle_language_edit, supports_language),
        )

        for field, visible in rows:
            field.setVisible(visible)
            label = self.video_labels.get(field)

            if label is not None:
                label.setVisible(visible)

        self._balance_parameter_rows(self.video_grid)

    def _check_login(self):
        # 登录检查不产出数据，完成弹窗不该报「保存位置」
        self._start_task(["-l"], "检查登录", has_output=False)

    def _start_video_task(self):
        bvid = self.bvid_edit.text().strip() or DEFAULT_BVID

        if not BVID_PATTERN.fullmatch(bvid):
            self._show_input_error("视频编号格式不正确。")
            return

        action = self.video_action.currentData()
        page_range = ""

        if action in {"subtitles", "danmaku"}:
            page_range = self._read_page_range(self.video_page_edit.text())

            if page_range is None:
                return

        self._start_task(
            self._video_args(page_range),
            f"视频采集：{self.video_action.currentText()}",
        )

    def _start_search_task(self):
        keyword = self.keyword_edit.text().strip()

        if not keyword:
            self._show_input_error("请输入搜索关键词。")
            self.keyword_edit.setFocus()
            return

        page_range = self._read_page_range(self.search_page_edit.text())

        if page_range is None:
            return

        self._start_task(
            self._search_args(page_range),
            f"关键词搜索：{keyword}",
        )

    def _start_user_video_task(self):
        mid = self.mid_edit.text().strip()

        if not mid.isdigit() or int(mid) <= 0:
            self._show_input_error("UP 主 MID 必须是大于 0 的数字。")
            self.mid_edit.setFocus()
            return

        self._start_task(self._user_args(), f"UP 主视频：{mid}")

    def _start_hot_search_task(self):
        self._start_task(self._hot_args(), "热搜搜索")

    @staticmethod
    def _normalize_page_range(value):
        value = value.strip()

        if not value:
            return ""

        try:
            start, end = parse_page_range(value)
        except Exception:
            return None

        return str(start) if start == end else f"{start},{end}"

    def _read_page_range(self, value):
        page_range = self._normalize_page_range(value)

        if page_range is None:
            self._show_input_error("页范围格式不正确，应填写 1 或 1,3。")

        return page_range

    def _start_task(self, args, title, has_output=True):
        if self._busy:
            return

        active_page = self.pages.currentIndex()
        self._task_title = title
        self._task_page = active_page
        self._task_has_output = has_output
        self._save_settings()
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
            self._refresh_project_data()
            self._set_busy(False, "已完成")
            self.statusBar().showMessage("任务完成", 5000)
            project_kind = {
                0: "video",
                1: "search",
                2: "user",
                3: "hot",
            }.get(self._task_page) if self._task_has_output else None
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
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._refresh_project_data()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR)))

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

        self._save_settings()
        event.accept()
