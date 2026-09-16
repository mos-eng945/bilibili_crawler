"""Bilibili 输出目录和文件名工具。"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def safe_filename(value):
    """移除 Windows 文件名不允许的字符。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value))
    return cleaned.rstrip(" .")


def get_video_dir(video_info):
    """根据 UP 主、标题和 BV 号生成视频输出目录。"""
    up_name = safe_filename(video_info.get("owner", {}).get("name") or "unknown")
    title = safe_filename(video_info.get("title") or "untitled")
    bvid = safe_filename(video_info.get("bvid") or "unknown")

    return BASE_DIR / "output" / f"{up_name}_{title}_{bvid}"
