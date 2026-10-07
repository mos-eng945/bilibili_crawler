"""输出目录结构和路径解析。

所有采集结果都落在 `output/` 下，按类别分成四个平级目录：

    output/
    ├── bvid/          视频数据
    ├── search/        关键词搜索
    ├── up/            UP 主视频
    └── hot_search/    热搜搜索

目录常量、路径构造函数，以及界面回查数据时用到的查找和统计函数都集中在
这里，避免同样的路径规则散落在各个爬虫和界面代码中。
"""

import re
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

OUTPUT_DIR = BASE_DIR / "output"
VIDEO_OUTPUT_DIR = OUTPUT_DIR / "bvid"
SEARCH_OUTPUT_DIR = OUTPUT_DIR / "search"
UP_OUTPUT_DIR = OUTPUT_DIR / "up"
HOT_OUTPUT_DIR = OUTPUT_DIR / "hot_search"

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(value):
    """移除 Windows 文件名不允许的字符。"""
    return _ILLEGAL_CHARS.sub("_", str(value)).rstrip(" .")


def run_timestamp():
    """返回用于目录和文件名的运行时间。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def timestamped_path(directory, prefix, count, suffix=".csv"):
    """生成带运行时间的输出文件路径。"""
    return Path(directory) / f"{prefix}_{run_timestamp()}_{count}{suffix}"


def get_video_dir(video_info):
    """生成视频输出目录：`bvid/{UP主}_{标题}_{BV号}/`。"""
    up_name = safe_filename(
        video_info.get("owner", {}).get("name") or "unknown"
    )
    title = safe_filename(video_info.get("title") or "untitled")
    bvid = safe_filename(video_info.get("bvid") or "unknown")
    return VIDEO_OUTPUT_DIR / f"{up_name}_{title}_{bvid}"


def get_search_dir(keyword, root=None):
    """生成关键词搜索目录：`search/{关键词}/`。"""
    root = root or SEARCH_OUTPUT_DIR
    return Path(root) / (safe_filename(keyword) or "search")


def get_up_dir(mid, name="", root=None):
    """生成 UP 主视频目录：`up/{MID}+{名字}/`。"""
    root = root or UP_OUTPUT_DIR
    name = str(name or "").strip()
    folder = f"{mid}+{safe_filename(name)}" if name else str(mid)
    return Path(root) / folder


def get_hot_run_dir(run_time):
    """生成某次热搜运行的目录：`hot_search/{运行时间}/`。"""
    return HOT_OUTPUT_DIR / run_time


def newest_path(paths):
    """按修改时间取最新的一个路径，空列表返回 None。"""
    paths = list(paths)
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None


def latest_directory_name(root):
    """返回目录下最近修改的子目录名，没有则返回空串。"""
    if not root.exists():
        return ""

    candidates = []

    for path in root.iterdir():
        if not path.is_dir():
            continue

        try:
            modified_at = path.stat().st_mtime
        except OSError:
            continue

        candidates.append((modified_at, path.name))

    return max(candidates)[1] if candidates else ""


def video_project_dir(bvid):
    """按 BV 号后缀找最新的视频目录。"""
    bvid = str(bvid or "").strip()

    if not bvid or not VIDEO_OUTPUT_DIR.exists():
        return None

    matches = [
        path
        for path in VIDEO_OUTPUT_DIR.iterdir()
        if path.is_dir() and path.name.endswith(f"_{bvid}")
    ]
    return newest_path(matches)


def search_project_dir(keyword):
    """关键词对应的搜索目录，不存在返回 None。"""
    if not str(keyword or "").strip():
        return None

    path = get_search_dir(keyword)
    return path if path.exists() else None


def find_user_dir(mid):
    """按 MID 前缀匹配 `{mid}` 或 `{mid}+*` 的最新目录。"""
    mid = str(mid or "").strip()

    if not mid or not UP_OUTPUT_DIR.exists():
        return None

    matches = [
        path
        for path in UP_OUTPUT_DIR.iterdir()
        if path.is_dir()
        and (path.name == mid or path.name.startswith(f"{mid}+"))
    ]
    return newest_path(matches)


def hot_project_dir():
    """最近一次热搜运行目录，没有运行时返回 None。"""
    if not HOT_OUTPUT_DIR.exists():
        return None

    runs = [path for path in HOT_OUTPUT_DIR.iterdir() if path.is_dir()]
    return newest_path(runs) or HOT_OUTPUT_DIR


def latest_search_keyword():
    """最近修改过的关键词目录名。"""
    return latest_directory_name(SEARCH_OUTPUT_DIR)


def latest_user_mid():
    """最近修改过的 UP 主目录里的 MID。"""
    return latest_directory_name(UP_OUTPUT_DIR).split("+", 1)[0]


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


def relative_display(path):
    """把绝对路径显示成 `output/...` 形式。"""
    try:
        return "output/" + Path(path).relative_to(OUTPUT_DIR).as_posix()
    except ValueError:
        return str(path)


def is_subtitle_json(path):
    """字幕 JSON 只是中间产物，浏览和统计时只保留 SRT。"""
    name = Path(path).name.lower()
    return name.startswith("subtitle_") and name.endswith(".json")
