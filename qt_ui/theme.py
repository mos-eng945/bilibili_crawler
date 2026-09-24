"""Qt application theme."""

from pathlib import Path


APP_STYLE = """
QWidget#AppRoot {
    background: #f4f5f7;
    color: #20242c;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QDialog {
    background: #f4f5f7;
    color: #20242c;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QDialog#CompletionDialog {
    background: #ffffff;
}
QLabel#CompletionBadge {
    color: #ffffff;
    background: #fb7299;
    border-radius: 23px;
    font-size: 24px;
    font-weight: 800;
}
QLabel#CompletionTitle {
    color: #20242c;
    font-size: 20px;
    font-weight: 800;
}
QLabel#CompletionMessage {
    color: #555c67;
    font-size: 13px;
    font-weight: 600;
}
QFrame#CompletionPanel {
    background: #f7f8fa;
    border: 1px solid #e1e4e9;
    border-radius: 8px;
}
QLabel#CompletionPanelLabel {
    color: #8a909b;
    font-size: 10px;
    font-weight: 700;
}
QLabel#CompletionPath {
    color: #353b44;
    font-size: 12px;
    font-weight: 600;
}
QWidget#Header {
    background: #ffffff;
    border-bottom: 1px solid #e1e4e9;
}
QLabel#LogoBadge {
    background: transparent;
    border: none;
}
QLabel {
    color: #20242c;
}
QLabel#AppTitle {
    color: #1f232a;
    font-size: 19px;
    font-weight: 700;
}
QLabel#AppCaption {
    color: #8a909b;
    font-size: 9px;
    font-weight: 700;
}
QLabel#StatusLabel {
    color: #3f4652;
    padding: 0 12px;
    border-radius: 7px;
    background: #f7f8fa;
    border: 1px solid #dfe3e8;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#HeaderButton {
    min-height: 34px;
    color: #373d47;
    background: #ffffff;
    border: 1px solid #d8dce2;
    font-weight: 600;
}
QPushButton#HeaderButton:hover {
    color: #20242c;
    background: #f7f8fa;
    border-color: #c4c9d1;
}
QWidget#Sidebar {
    background: #f1f0f4;
    border-right: 1px solid #e2e0e6;
}
QWidget#SidebarRail {
    background: #e9e7ed;
    border: none;
}
QPushButton#RailButton {
    padding: 0;
    border: none;
    border-radius: 5px;
    background: transparent;
    color: #7d7683;
    font-size: 18px;
    font-weight: 700;
}
QPushButton#RailButton:hover {
    background: #dedbe3;
    color: #312d35;
}
QPushButton#RailButton:pressed {
    background: #d3cfd9;
}
QLabel#SidebarSection {
    color: #88818e;
    font-size: 10px;
    font-weight: 700;
}
QPushButton#NavButton {
    min-height: 44px;
    color: #57515d;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0 13px;
    text-align: left;
    font-weight: 600;
}
QPushButton#NavButton:hover {
    color: #312d35;
    background: #e6e3e9;
    border-color: #dcd8e0;
}
QPushButton#NavButton:checked {
    color: #ffffff;
    background: #fb7299;
    border-color: #fb7299;
    font-weight: 700;
}
QLabel#PageTitle {
    color: #20242c;
    font-size: 23px;
    font-weight: 800;
}
QLabel#PageMeta {
    color: #767c87;
    font-size: 12px;
}
QLabel#PageBadge {
    color: #835268;
    background: #fff0f5;
    border: 1px solid #f8c7d8;
    border-radius: 7px;
    padding: 4px 11px;
    font-weight: 700;
}
QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #e0e3e8;
    border-radius: 8px;
}
QLabel#MetricLabel {
    color: #818792;
    font-size: 10px;
    font-weight: 700;
}
QLabel#MetricValue {
    color: #282d35;
    font-size: 17px;
    font-weight: 800;
}
QLabel#MetricValueAccent {
    color: #e95482;
    font-size: 17px;
    font-weight: 800;
}
QLabel#OutputPath {
    color: #5e6570;
    background: #f7f8fa;
    border: 1px solid #dcdfe5;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#SideOutputCount {
    color: #282d35;
    font-size: 15px;
    font-weight: 800;
}
QGroupBox#SideOutput {
    border-top: 3px solid #8f8a99;
}
QFrame#OutputBar {
    background: #ffffff;
    border: 1px solid #e0e3e8;
    border-radius: 8px;
}
QPushButton#SmallIconButton {
    min-height: 28px;
    max-height: 28px;
    min-width: 28px;
    max-width: 28px;
    padding: 0;
    border: 1px solid #d8dce2;
    border-radius: 6px;
    background: #ffffff;
}
QPushButton#SmallIconButton:hover {
    background: #f5f6f8;
    border-color: #bcc2cb;
}
QGroupBox {
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    background: #ffffff;
    margin-top: 14px;
    padding: 20px 18px 16px 18px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #3c424c;
    background: #ffffff;
}
QGroupBox#PreviewGroup {
    border-top: 3px solid #fb7299;
}
QLabel#FieldHint {
    color: #7d838e;
    font-size: 11px;
}
QLabel#PreviewValue {
    color: #424852;
    background: #f7f8fa;
    border: 1px solid #e1e4e9;
    border-radius: 6px;
    padding: 7px 9px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#ExecutionSummary {
    color: #424852;
    background: #f7f8fa;
    border: 1px solid #e1e4e9;
    border-radius: 6px;
    padding: 10px 11px;
    font-size: 12px;
    font-weight: 600;
}
QToolButton#AdvancedToggle {
    color: #68707c;
    background: transparent;
    border: none;
    padding: 3px 2px;
    font-size: 11px;
    font-weight: 600;
}
QToolButton#AdvancedToggle:hover {
    color: #e95482;
}
QLabel#PreviewTitle {
    color: #262b33;
    font-size: 18px;
    font-weight: 800;
}
QLabel#PreviewMeta {
    color: #767c87;
    font-size: 11px;
}
QLineEdit, QComboBox, QSpinBox {
    min-height: 36px;
    border: 1px solid #d5d9df;
    border-radius: 6px;
    background: #ffffff;
    color: #20242c;
    padding: 0 9px;
    selection-background-color: #fb7299;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
    border-color: #bfc5cd;
}
QSpinBox {
    padding-right: 30px;
}
QSpinBox::up-button,
QSpinBox::down-button {
    subcontrol-origin: border;
    width: 24px;
    background: #f4f5f7;
    border: none;
    border-left: 1px solid #e1e4e9;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    border-bottom: 1px solid #e1e4e9;
    border-top-right-radius: 5px;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 5px;
}
QSpinBox::up-arrow {
    image: url("__SPIN_UP_ARROW__");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow {
    image: url("__SPIN_DOWN_ARROW__");
    width: 10px;
    height: 10px;
}
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background: #eceef1;
}
QSpinBox::up-button:pressed,
QSpinBox::down-button:pressed {
    background: #e2e5e9;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #fb7299;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background: #f5f6f8;
    color: #a2a7af;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox::down-arrow {
    image: url("__COMBO_DOWN_ARROW__");
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #20242c;
    border: 1px solid #d5d9df;
    selection-background-color: #fb7299;
    selection-color: #ffffff;
    outline: none;
}
QPushButton {
    min-height: 34px;
    padding: 0 14px;
    border: 1px solid #d6dae0;
    border-radius: 6px;
    background: #ffffff;
    color: #383e47;
}
QPushButton:hover {
    background: #f6f7f9;
    border-color: #bcc2ca;
}
QPushButton:pressed {
    background: #eceef1;
}
QPushButton:disabled {
    background: #f1f2f4;
    color: #adb2ba;
    border-color: #e2e5e9;
}
QPushButton#PrimaryButton {
    background: #fb7299;
    color: #ffffff;
    border: 1px solid #fb7299;
    font-weight: 700;
    padding: 0 20px;
}
QPushButton#PrimaryButton:hover {
    background: #e95b86;
    border-color: #e95b86;
}
QPushButton#PrimaryButton:pressed {
    background: #d94b77;
    border-color: #d94b77;
}
QPushButton#StopButton {
    background: #d15c5c;
    color: #ffffff;
    border-color: #d15c5c;
    font-weight: 700;
}
QPushButton#StopButton:hover {
    background: #bf4c4c;
    border-color: #bf4c4c;
}
QPlainTextEdit {
    border: 1px solid #252a32;
    border-radius: 8px;
    background: #1b1f26;
    color: #dfe3e8;
    padding: 12px;
    selection-background-color: #fb7299;
}
QPlainTextEdit#CommandPreview {
    background: #f7f8fa;
    color: #424852;
    border: 1px solid #dfe3e8;
    padding: 8px;
}
QPlainTextEdit#FullContentEdit {
    background: #ffffff;
    color: #2a3038;
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    padding: 14px;
    selection-background-color: #f9c4d5;
    selection-color: #2a3038;
}
QPlainTextEdit#VideoDescription {
    background: #f7f8fa;
    color: #424852;
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #f9c4d5;
    selection-color: #2a3038;
}
QTableWidget, QTableView {
    background: #ffffff;
    alternate-background-color: #f8f9fa;
    border: 1px solid #e1e4e9;
    border-radius: 6px;
    color: #353b44;
    gridline-color: #eceef1;
    selection-background-color: #ffe8f0;
    selection-color: #692b42;
}
QTableWidget::item, QTableView::item {
    padding: 5px;
}
QHeaderView::section {
    background: #f5f6f8;
    color: #555c67;
    border: none;
    border-bottom: 1px solid #dfe3e8;
    padding: 7px;
    font-weight: 700;
}
QTabWidget#PreviewTabs::pane {
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    background: #ffffff;
    top: -1px;
}
QTabWidget#PreviewTabs QTabBar::tab {
    background: #eceef1;
    color: #656c77;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-weight: 700;
}
QTabWidget#PreviewTabs QTabBar::tab:selected {
    background: #ffffff;
    color: #e95482;
}
QLabel#ReportSection {
    color: #3b414b;
    font-size: 14px;
    font-weight: 800;
}
QFrame#VideoInfoPanel {
    background: #f7f8fa;
    border: 1px solid #dfe3e8;
    border-radius: 8px;
}
QLabel#VideoInfoLabel {
    color: #7d838e;
    font-size: 10px;
    font-weight: 700;
}
QLabel#VideoInfoValue {
    color: #333943;
    font-size: 12px;
    font-weight: 700;
}
QFrame#LogEmpty {
    background: #ffffff;
    border: 1px solid #e1e4e9;
    border-radius: 8px;
}
QLabel#EmptyTitle {
    color: #333943;
    font-size: 18px;
    font-weight: 800;
}
QLabel#EmptyCaption {
    color: #7d838e;
    font-size: 12px;
}
QProgressBar {
    border: none;
    background: transparent;
    max-height: 3px;
}
QProgressBar::chunk {
    background: #fb7299;
}
QStatusBar {
    background: #ffffff;
    color: #6f7580;
    border-top: 1px solid #dfe3e8;
}
"""


_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
APP_STYLE = APP_STYLE.replace(
    "__SPIN_UP_ARROW__",
    (_ASSET_DIR / "chevron-up.svg").as_posix(),
).replace(
    "__SPIN_DOWN_ARROW__",
    (_ASSET_DIR / "chevron-down.svg").as_posix(),
).replace(
    "__COMBO_DOWN_ARROW__",
    (_ASSET_DIR / "chevron-down.svg").as_posix(),
)
