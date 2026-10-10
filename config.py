"""项目级默认配置和通用参数解析。"""

import argparse
from pathlib import Path

# 项目根目录；资源、输出、登录状态都相对它定位
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
# 采集任务的命令行入口，GUI 和命令行都指向同一个文件
ENTRY_SCRIPT = BASE_DIR / "main.py"
DEFAULT_BVID = "BV1UT42167xb"
# 采集结果统一落在 output/ 下，按类别分四个平级目录
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_OUTPUT_DIR = OUTPUT_DIR / "video"
SEARCH_OUTPUT_DIR = OUTPUT_DIR / "search"
UP_OUTPUT_DIR = OUTPUT_DIR / "up"
HOT_OUTPUT_DIR = OUTPUT_DIR / "hot"


class ParsedPageRange(tuple):
    """记录页码范围是否显式填写了结束页。"""

    has_explicit_end: bool

    def __new__(cls, start, end, has_explicit_end):
        instance = super().__new__(cls, (start, end))
        instance.has_explicit_end = has_explicit_end
        return instance


def parse_page_range(value):
    """把 START 或 START,END 转换成包含首尾的整数范围。"""
    parts = value.split(",")

    if len(parts) > 2:
        raise argparse.ArgumentTypeError("范围格式应为 START,END")

    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) == 2 else start
    except ValueError as exc:
        raise argparse.ArgumentTypeError("页码范围必须是整数") from exc

    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("页码必须满足 1 <= START <= END")

    return ParsedPageRange(start, end, len(parts) == 2)


def resolve_search_page_range(value):
    """解析关键词搜索页范围，单值 N 表示第 1 到第 N 页。"""
    if value is None:
        return 1, 1

    start, end = value
    has_explicit_end = getattr(value, "has_explicit_end", True)

    if not has_explicit_end:
        return 1, end

    return start, end
