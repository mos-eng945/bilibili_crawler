"""Qt application theme."""

from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPalette


_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
_STYLE_PATH = _ASSET_DIR / "app.qss"


def _load_style():
    """读取 QSS，并把资源占位符替换成绝对路径。"""
    style = _STYLE_PATH.read_text(encoding="utf-8")

    return (
        style.replace(
            "__SPIN_UP_ARROW__",
            (_ASSET_DIR / "chevron-up.svg").as_posix(),
        )
        .replace(
            "__SPIN_DOWN_ARROW__",
            (_ASSET_DIR / "chevron-down.svg").as_posix(),
        )
        .replace(
            "__COMBO_DOWN_ARROW__",
            (_ASSET_DIR / "chevron-down.svg").as_posix(),
        )
        .replace(
            "__CHECK_MARK__",
            (_ASSET_DIR / "check.svg").as_posix(),
        )
    )


APP_STYLE = _load_style()


def apply_palette(app):
    """强制浅色调色板，避免系统深色模式把未写样式的控件画成黑色。"""
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f4f5f7",
        QPalette.ColorRole.WindowText: "#20242c",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f8f9fa",
        QPalette.ColorRole.Text: "#20242c",
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: "#383e47",
        QPalette.ColorRole.Highlight: "#fb7299",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: "#20242c",
        QPalette.ColorRole.PlaceholderText: "#a2a7af",
    }

    for role, color in colors.items():
        palette.setColor(role, QColor(color))

    app.setPalette(palette)


def icon(name):
    """加载 assets 下的图标，取代 Qt 自带那套标准图标。"""
    return QIcon(str(_ASSET_DIR / name))
