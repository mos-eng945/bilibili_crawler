"""爬虫共用的请求、格式化、并发和文件输出工具。"""

import csv
import html
import json
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

T = TypeVar("T")

SEARCH_DEFAULT_WORKERS = 2
SEARCH_MAX_WORKERS = 5
SEARCH_DEFAULT_PAGE_SIZE = 30
SEARCH_MAX_PAGE_SIZE = 50
SEARCH_MAX_RESULTS = 1000
SEARCH_RETRY_ATTEMPTS = 5
SEARCH_RETRY_DELAY_SECONDS = 1
CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")
_LOG_LOCK = threading.Lock()
_LOG_CONTEXT = threading.local()

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

# 日志


def set_log_prefix(prefix):
    """设置当前线程的日志前缀。"""
    _LOG_CONTEXT.prefix = str(prefix or "")


def clear_log_prefix():
    """清除当前线程的日志前缀。"""
    _LOG_CONTEXT.prefix = ""


def log(message):
    """原子输出一行或多行日志，并自动加线程前缀。"""
    prefix = getattr(_LOG_CONTEXT, "prefix", "")
    lines = str(message).splitlines() or [""]

    with _LOG_LOCK:
        for line in lines:
            text = line
            if prefix:
                text = f"[{prefix}] {line}"
            print(text, flush=True)


# 文本清理


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
        return "https://" + url.removeprefix("http://")

    return url


_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(value, max_length=None):
    """移除 Windows 文件名不允许的字符。"""
    name = _ILLEGAL_CHARS.sub("_", str(value)).rstrip(" .")

    if max_length is not None and len(name) > max_length:
        name = name[:max_length].rstrip(" .")

    return name


# 时间处理


def parse_duration_seconds(value):
    """把秒数、分:秒或时:分:秒转换成整数秒。

    示例：
        "90" -> 90
        "1:30" -> 90
        "1:02:03" -> 3723

    无法解析、格式错误或包含负数时返回 0。
    """
    if isinstance(value, (int, float)):
        seconds = int(value)
        if seconds < 0:
            return 0
        return seconds

    text = str(value or "").strip()

    if not text:
        return 0

    raw_parts = text.split(":")
    if not 1 <= len(raw_parts) <= 3:
        return 0

    parts = []
    for raw_part in raw_parts:
        try:
            part = int(raw_part)
        except ValueError:
            return 0

        if part < 0:
            return 0

        parts.append(part)

    if len(parts) == 1:
        return parts[0]

    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds

    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def _timestamp_to_china_datetime(timestamp):
    """把秒级时间戳转换成中国时区的时间，转换失败时返回 None。

    示例：
        0 -> datetime(1970, 1, 1, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        "bad" -> None
    """
    try:
        return datetime.fromtimestamp(int(timestamp), tz=CHINA_TIMEZONE)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def format_published_at(timestamp):
    """把秒级时间戳转换成中国时区的 ISO 时间。

    示例：
        0 -> "1970-01-01T08:00:00+08:00"
    """
    date_time = _timestamp_to_china_datetime(timestamp)
    if date_time is None:
        return ""

    return date_time.isoformat()


def format_china_time(timestamp):
    """把秒级时间戳转换成中国时区的可读时间。

    示例：
        0 -> "1970-01-01 08:00:00"
    """
    date_time = _timestamp_to_china_datetime(timestamp)
    if date_time is None:
        return ""

    return date_time.strftime("%Y-%m-%d %H:%M:%S")


def format_milliseconds(milliseconds):
    """把毫秒偏移转换成 HH:MM:SS。

    示例：
        3723000 -> "01:02:03"
    """
    try:
        total_seconds = max(0, int(milliseconds)) // 1000
    except (TypeError, ValueError, OverflowError):
        return ""

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# B 站数据映射
# 视频分区：接口只回 tid 编号、tname 长期为空，名字本地维护。
# 名字直接取自官方分区树 x/v2/region/index（tid -> 分区名）。
ZONE_NAMES = {
    1: "动画",
    3: "音乐",
    4: "游戏",
    5: "娱乐",
    11: "电视剧",
    13: "番剧",
    17: "单机游戏",
    19: "Mugen",
    20: "宅舞",
    21: "日常",
    22: "鬼畜调教",
    23: "电影",
    24: "MAD·AMV",
    25: "MMD·3D",
    26: "音MAD",
    27: "综合",
    28: "原创音乐",
    29: "音乐现场",
    30: "VOCALOID·UTAU",
    31: "翻唱",
    32: "完结动画",
    33: "连载动画",
    36: "知识",
    37: "人文·历史",
    47: "同人·手书",
    51: "资讯",
    59: "演奏",
    65: "网络游戏",
    71: "综艺",
    75: "动物综合",
    76: "美食制作",
    83: "其他国家",
    85: "小剧场",
    86: "特摄",
    95: "数码",
    119: "鬼畜",
    121: "GMV",
    122: "野生技能协会",
    124: "社科·法律·心理",
    126: "人力VOCALOID",
    127: "教程演示",
    129: "舞蹈",
    130: "音乐综合",
    136: "音游",
    137: "明星综合",
    138: "搞笑",
    145: "欧美电影",
    146: "日本电影",
    147: "华语电影",
    152: "官方延伸",
    153: "国产动画",
    154: "舞蹈综合",
    155: "时尚",
    156: "舞蹈教程",
    157: "美妆护肤",
    158: "穿搭",
    159: "时尚潮流",
    160: "生活",
    161: "手工",
    162: "绘画",
    164: "健身",
    167: "国创",
    168: "国产原创相关",
    169: "布袋戏",
    170: "资讯",
    171: "电子竞技",
    172: "手机游戏",
    173: "桌游棋牌",
    176: "汽车生活",
    177: "纪录片",
    178: "科学·探索·自然",
    179: "军事",
    180: "社会·美食·旅行",
    181: "影视",
    182: "影视杂谈",
    183: "影视剪辑",
    184: "预告·资讯",
    185: "国产剧",
    187: "海外剧",
    188: "科技",
    193: "MV",
    195: "动态漫·广播剧",
    198: "街舞",
    199: "明星舞蹈",
    200: "国风舞蹈",
    201: "科学科普",
    202: "资讯",
    203: "热点",
    204: "环球",
    205: "社会",
    206: "综合",
    207: "财经商业",
    208: "校园学习",
    209: "职业职场",
    210: "模玩·周边",
    211: "美食",
    212: "美食侦探",
    213: "美食测评",
    214: "田园美食",
    215: "美食记录",
    216: "鬼畜剧场",
    217: "动物圈",
    218: "喵星人",
    219: "汪星人",
    220: "动物二创",
    221: "野生动物",
    222: "小宠异宠",
    223: "汽车",
    227: "购车攻略",
    228: "人文历史",
    229: "设计·创意",
    230: "软件应用",
    231: "计算机技术",
    232: "科工机械",
    233: "极客DIY",
    234: "运动",
    235: "篮球",
    236: "竞技体育",
    237: "运动文化",
    238: "运动综合",
    239: "家居房产",
    240: "摩托车",
    241: "娱乐杂谈",
    242: "娱乐粉丝创作",
    243: "乐评盘点",
    244: "音乐教学",
    245: "赛车",
    246: "改装玩车",
    247: "新能源车",
    248: "房车",
    249: "足球",
    250: "出行",
    251: "三农",
    252: "仿妆cos",
    253: "动漫杂谈",
    254: "亲子",
    255: "颜值·网红舞",
    256: "短片",
    257: "配音",
    258: "汽车知识科普",
    259: "AI影像",
    260: "影视整活",
    261: "影视综合",
    262: "CP安利",
    263: "颜值安利",
    264: "娱乐资讯",
    265: "AI音乐",
    266: "音乐粉丝饭拍",
    267: "电台",
    65539: "游戏中心",
    65541: "专栏",
    65545: "放映厅",
    65549: "工房集市",
    65550: "游戏赛事",
    65551: "小黑屋",
    65552: "全区排行榜",
    65553: "活动中心",
    65555: "漫画",
    65556: "原创排行榜",
    65557: "公开课",
    65559: "VLOG",
    65560: "课堂",
    65563: "新歌热榜",
}


def zone_name(tid):
    """按分区编号返回分区名，未收录返回空串。"""
    return ZONE_NAMES.get(tid, "")


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


# 路径与文件


def run_timestamp():
    """返回当前本地时间戳，格式为 YYYYMMDD_HHMMSS，用于标识每次运行。

    示例：2026-10-28 14:35:07 -> "20261028_143507"
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def timestamped_path(directory, prefix, count, suffix=".csv"):
    """生成带运行时间的输出文件路径。

    格式：{directory}/{prefix}_{YYYYMMDD_HHMMSS}_{count}{suffix}
    示例："output"、"video"、12 -> "output/video_20261028_143507_12.csv"
    """
    return Path(directory) / f"{prefix}_{run_timestamp()}_{count}{suffix}"


def write_csv(path, columns, rows, append=False):
    """按固定列顺序写入 CSV。

    append=True 表示追加模式，append=False 表示写入模式。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    mode = "w"
    if append:
        mode = "a"

    write_header = True
    if append and path.exists() and path.stat().st_size > 0:
        write_header = False

    with open(path, mode, newline="", encoding="utf-8-sig") as file:
        # 行里可能带未列出的字段（如搜索结果没有分享数），按 columns 写即可
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        if write_header:
            writer.writeheader()

        writer.writerows(rows)


def write_json(path, data):
    """写入 UTF-8 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return path


# 并发任务与请求重试


def run_concurrently(function, values, workers, label, on_progress=None):
    """按配置并发或顺序执行任务，并按输入顺序返回结果,返回值为function()的返回值。

    未提供 on_progress 时，每完成 10 个任务及全部完成时打印进度。
    """
    total = len(values)

    if total == 0:
        return []

    requested_workers = int(workers)
    if requested_workers < 1:
        requested_workers = 1

    worker_count = min(requested_workers, total)

    results = [None] * total
    future_to_index = {}

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for index, value in enumerate(values):
            future = executor.submit(function, value)
            future_to_index[future] = index

        completed = 0
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()
            completed += 1

            if on_progress is not None:
                on_progress(completed, total)
            elif completed == total or completed % 10 == 0:
                print(f"{label}进度：{completed}/{total}")

    return results


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
