"""爬虫共用的请求、格式化、并发和文件输出工具。"""

import csv
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, TypeVar
from zoneinfo import ZoneInfo

from bilibili_api import get_up_follower_count, get_video_info

T = TypeVar("T")

SEARCH_DEFAULT_WORKERS = 2
SEARCH_MAX_WORKERS = 10
SEARCH_RETRY_ATTEMPTS = 3
SEARCH_RETRY_DELAY_SECONDS = 1
CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")
SEARCH_COLUMNS = [
    "bvid",
    "title",
    "published_at",
    "author",
    "mid",
    "partition",
    "tags",
    "duration_seconds",
    "cover_url",
    "like",
    "comment_count",
    "favorite_count",
    "share_count",
    "author_follower_count",
    "play_count",
    "danmaku_count",
]


def clean_html_text(value):
    """移除搜索结果标题中的高亮标签。"""
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return html.unescape(text).strip()


def normalize_url(value):
    """把 B 站常见的协议相对 URL 转成 HTTPS。"""
    url = str(value or "").strip()

    if url.startswith("//"):
        return f"https:{url}"

    if url.startswith("http://"):
        return f"https://{url[7:]}"

    return url


def parse_duration_seconds(value):
    """把分:秒或秒数转换成整数秒。"""
    if isinstance(value, (int, float)):
        return max(0, int(value))

    text = str(value or "").strip()

    if not text:
        return 0

    try:
        parts = [int(part) for part in text.split(":")]
    except ValueError:
        return 0

    if not 1 <= len(parts) <= 3:
        return 0

    seconds = 0

    for part in parts:
        seconds = seconds * 60 + max(0, part)

    return seconds


def format_published_at(timestamp):
    """把秒级时间戳转换成中国时区的 ISO 时间。"""
    try:
        return datetime.fromtimestamp(
            int(timestamp),
            tz=CHINA_TIMEZONE,
        ).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def request_with_retry(
    function: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """请求失败时短暂等待并重试。"""
    for attempt in range(1, SEARCH_RETRY_ATTEMPTS + 1):
        try:
            return function(*args, **kwargs)
        except RuntimeError:
            if attempt == SEARCH_RETRY_ATTEMPTS:
                raise

            time.sleep(SEARCH_RETRY_DELAY_SECONDS * attempt)

    raise RuntimeError("请求重试失败")


def build_video_row(
    *,
    bvid,
    title,
    published_at,
    author,
    mid,
    partition,
    tags,
    duration_seconds,
    cover_url,
    like,
    comment_count,
    favorite_count,
    share_count,
    author_follower_count,
    play_count,
    danmaku_count,
):
    """按搜索和 UP 视频共用的 CSV 结构生成一行。"""
    return {
        "bvid": bvid or "",
        "title": clean_html_text(title),
        "published_at": published_at or "",
        "author": author or "",
        "mid": mid or "",
        "partition": partition or "",
        "tags": tags or "",
        "duration_seconds": duration_seconds or 0,
        "cover_url": normalize_url(cover_url),
        "like": like or 0,
        "comment_count": comment_count or 0,
        "favorite_count": favorite_count or 0,
        "share_count": share_count or 0,
        "author_follower_count": author_follower_count or 0,
        "play_count": play_count or 0,
        "danmaku_count": danmaku_count or 0,
    }


def write_csv(path, columns, rows, append=False):
    """按固定列顺序写入 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    write_header = not append or not path.exists() or path.stat().st_size == 0

    with open(path, mode, newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)

        if write_header:
            writer.writeheader()

        writer.writerows(rows)


def write_json(path, data):
    """写入 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return path


def run_concurrently(function, values, workers, label):
    """按配置并发或顺序执行任务，并按输入顺序返回结果。"""
    total = len(values)

    if total == 0:
        return []

    worker_count = min(max(1, int(workers)), total)

    if worker_count == 1:
        results = []

        for value in values:
            results.append(function(value))
            completed = len(results)
            if completed == total or completed % 5 == 0:
                print(f"{label}进度：{completed}/{total}")

        return results

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = []

        for result in executor.map(function, values):
            results.append(result)
            completed = len(results)
            if completed == total or completed % 5 == 0:
                print(f"{label}进度：{completed}/{total}")

    return results


def fetch_video_info_safely(bvid, cookie):
    """请求视频详情，失败时返回 None。"""
    try:
        return request_with_retry(get_video_info, bvid, cookie)
    except RuntimeError as exc:
        print(f"视频 {bvid} 详情获取失败，使用搜索结果：{exc}")
        return None


def fetch_follower_count_safely(mid, author, cookie):
    """请求作者粉丝数，失败时返回 0。"""
    try:
        return request_with_retry(get_up_follower_count, mid, cookie)
    except RuntimeError as exc:
        print(f"作者 {author or mid} 粉丝数获取失败：{exc}")
        return 0
