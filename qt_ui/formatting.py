"""Data labels and display formatting."""

import re
from pathlib import Path

COLUMN_LABELS = {
    "bvid": "视频编号",
    "搜索关键词": "搜索关键词",
    "title": "标题",
    "published_at": "发布时间",
    "author": "作者",
    "mid": "作者编号",
    "partition": "分区",
    "tags": "标签",
    "duration_seconds": "视频时长",
    "cover_url": "封面地址",
    "like": "点赞",
    "comment_count": "评论数",
    "favorite_count": "收藏数",
    "share_count": "分享数",
    "author_follower_count": "作者粉丝",
    "play_count": "播放量",
    "danmaku_count": "弹幕数",
    "view": "播放量",
    "coin": "投币数",
    "favorite": "收藏数",
    "share": "分享数",
    "reply": "评论数",
    "danmaku": "弹幕数",
    "up_follower_count": "UP 主粉丝",
    "up_name": "UP 主",
    "description": "简介",
    "rank": "排名",
    "keyword": "热搜词",
    "show_name": "展示名称",
    "heat_score": "热度",
    "status": "状态",
    "error": "错误",
    "rpid": "评论编号",
    "user_name": "用户",
    "user_level": "等级",
    "sex": "性别",
    "vip": "大会员",
    "message": "评论内容",
    "ctime_text": "评论时间",
    "reply_count": "回复数",
    "state": "评论状态",
    "ip_location": "IP属地",
    "image_urls": "图片地址",
    "时间(ms)": "出现时间",
    "出现时间": "出现时间",
    "内容": "弹幕内容",
    "颜色": "颜色",
    "模式": "模式",
    "用户Hash": "用户标识",
    "弹幕id": "弹幕编号",
    "权重": "权重",
    "哈希": "用户标识",
    "发送时间": "发送时间",
    "弹幕池": "弹幕池",
    "序号": "序号",
    "开始": "开始时间",
    "结束": "结束时间",
    "字幕内容": "字幕内容",
}
NUMBER_COLUMNS = {
    "rank",
    "heat_score",
    "like",
    "comment_count",
    "favorite_count",
    "share_count",
    "author_follower_count",
    "play_count",
    "danmaku_count",
    "view",
    "coin",
    "favorite",
    "share",
    "reply",
    "danmaku",
    "up_follower_count",
    "user_level",
    "vip",
    "reply_count",
    "权重",
}

KEY_COLUMN_ORDER = {
    "search": (
        "搜索关键词",
        "title",
        "author",
        "partition",
        "duration_seconds",
        "play_count",
        "like",
        "comment_count",
        "favorite_count",
        "published_at",
        "share_count",
        "author_follower_count",
        "danmaku_count",
        "tags",
        "cover_url",
        "bvid",
        "mid",
    ),
    "comments": (
        "user_name",
        "message",
        "ctime_text",
        "like",
        "reply_count",
        "user_level",
        "sex",
        "vip",
        "state",
        "ip_location",
        "rpid",
        "mid",
        "image_urls",
    ),
    "hot_search": (
        "keyword",
        "heat_score",
        "rank",
        "status",
        "show_name",
        "error",
    ),
    "danmaku": (
        "弹幕id",
        "出现时间",
        "权重",
        "内容",
        "哈希",
        "发送时间",
        "弹幕池",
    ),
    "video_info": (
        "title",
        "up_name",
        "published_at",
        "view",
        "like",
        "reply",
        "favorite",
        "coin",
        "danmaku",
        "up_follower_count",
        "share",
        "description",
    ),
}


def format_number(value):
    """把较大数字转换成更容易阅读的中文单位。"""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return str(value or "")

    if abs(number) >= 10000:
        return f"{number / 10000:.1f} 万"

    return f"{number:,}"


def shorten_user_hash(value, visible_chars=8):
    """压缩预览表格里的匿名用户标识。"""
    text = str(value or "").strip()

    if len(text) <= visible_chars + 3:
        return text

    return f"{text[:visible_chars]}..."


def format_preview_value(column, value):
    """按列类型整理预览表格中的值。"""
    if value is None:
        return ""

    if column in NUMBER_COLUMNS:
        return format_number(value)

    if column == "published_at":
        text = str(value).replace("T", " ")
        return text[:16]

    if column == "duration_seconds":
        try:
            total_seconds = max(0, int(value))
        except (TypeError, ValueError):
            return str(value)

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{hours}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes}:{seconds:02d}"
        )

    if column == "status":
        return {
            "success": "成功",
            "failed": "失败",
        }.get(str(value).lower(), str(value))

    if column == "state":
        return "正常" if str(value) == "0" else str(value)

    if column == "时间(ms)":
        try:
            milliseconds = int(value)
            seconds, _ = divmod(milliseconds, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (TypeError, ValueError):
            return str(value)

    if column in {"开始", "结束"}:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return str(value)

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"
            if hours
            else f"{int(minutes):02d}:{seconds:06.3f}"
        )

    return str(value)


def friendly_video_name(folder_name):
    """把 output 里的视频目录名整理成易读名称。"""
    first, separator, rest = folder_name.partition("_")

    if separator and first.startswith("BV"):
        return f"{rest} · {first}"

    parts = folder_name.rsplit("_", 1)

    if len(parts) != 2 or not parts[1].startswith("BV"):
        return folder_name

    base_name = parts[0]

    if "_" in base_name:
        up_name, title = base_name.split("_", 1)
        return f"{title} · {up_name}"

    return base_name


def friendly_file_name(path):
    """把数据文件名整理成易读名称，供列表和浏览弹窗共用。"""
    path = Path(path)
    filename = path.name

    if filename == "video_info.json":
        return "视频概览"

    if filename.startswith("comments_"):
        return "评论"

    if filename.startswith("danmaku_"):
        stem = path.stem
        match = re.search(r"_p(\d+)$", stem)

        if match:
            part = stem[len("danmaku_"):match.start()]
            number = match.group(1)
            return (
                f"弹幕 · {part} (P{number})"
                if part
                else f"弹幕 P{number}"
            )

        return f"弹幕 · {stem[len('danmaku_'):]}"

    if filename.startswith("subtitle_"):
        match = re.search(r"_p(\d+)_(.+)\.(json|srt)$", filename)

        if match:
            page, language, suffix = match.groups()
            return f"字幕 P{page} · {language} · {suffix.upper()}"

        return "字幕"

    if filename == "hot_list.csv":
        return "热搜汇总"

    if filename.startswith("search_"):
        return f"搜索结果 · {path.parent.name}{_count_suffix(path)}"

    if filename.startswith("videos_"):
        return f"UP 主视频 · {path.parent.name}{_count_suffix(path)}"

    return path.stem


def _count_suffix(path):
    parts = path.stem.rsplit("_", 1)

    if len(parts) == 2 and parts[1].isdigit():
        return f" · {parts[1]} 条"

    return ""
