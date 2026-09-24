"""Data labels and display formatting."""

from datetime import datetime
from pathlib import Path

COLUMN_LABELS = {
    "bvid": "视频编号",
    "搜索关键词": "搜索关键词",
    "title": "标题",
    "published_at": "发布时间",
    "author": "作者",
    "mid": "作者编号",
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
    "result_file": "结果文件",
    "status": "状态",
    "error": "错误",
    "rpid": "评论编号",
    "user_name": "用户",
    "user_level": "等级",
    "message": "评论内容",
    "ctime": "评论时间",
    "reply_count": "回复数",
    "state": "评论状态",
    "image_urls": "图片地址",
    "时间(ms)": "出现时间",
    "内容": "弹幕内容",
    "颜色": "颜色",
    "模式": "模式",
    "用户Hash": "用户标识",
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
    "reply_count",
}

KEY_COLUMN_ORDER = {
    "search": (
        "搜索关键词",
        "title",
        "author",
        "play_count",
        "like",
        "comment_count",
        "favorite_count",
        "published_at",
        "share_count",
        "author_follower_count",
        "danmaku_count",
        "bvid",
        "mid",
    ),
    "comments": (
        "user_name",
        "message",
        "ctime",
        "like",
        "reply_count",
        "user_level",
        "state",
        "rpid",
        "mid",
        "image_urls",
    ),
    "hot_search": (
        "keyword",
        "heat_score",
        "rank",
        "status",
        "result_file",
        "show_name",
        "error",
    ),
    "danmaku": (
        "内容",
        "时间(ms)",
        "颜色",
        "模式",
        "用户Hash",
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

    if column == "ctime":
        try:
            return datetime.fromtimestamp(int(value)).strftime(
                "%Y-%m-%d %H:%M"
            )
        except (TypeError, ValueError, OSError):
            return str(value)

    if column == "published_at":
        text = str(value).replace("T", " ")
        return text[:16]

    if column == "result_file":
        text = str(value or "").strip()
        return Path(text).name if text else "未生成"

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
