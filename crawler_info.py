"""Bilibili 视频信息下载器。"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from bilibili_api import (
    get_cookie_header,
    get_up_follower_count,
    get_video_info,
)
from login import ensure_login
from main import DEFAULT_BVID
from video_paths import get_video_dir

CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")


def format_published_at(timestamp):
    """把秒级时间戳转换成中国时区的 ISO 时间。"""
    return datetime.fromtimestamp(timestamp, tz=CHINA_TIMEZONE).isoformat()


def crawl_video_info(bvid=DEFAULT_BVID):
    """获取视频信息并保存到对应 BV 目录。"""
    cookie = get_cookie_header()
    data = get_video_info(bvid, cookie)
    stat = data.get("stat", {})
    owner = data.get("owner", {})
    mid = owner.get("mid")

    if not mid:
        raise RuntimeError(f"视频 {bvid} 没有返回 UP 主 mid")

    result = {
        "title": data.get("title", ""),
        "like": stat.get("like", 0),
        "coin": stat.get("coin", 0),
        "favorite": stat.get("favorite", 0),
        "share": stat.get("share", 0),
        "published_at": format_published_at(data.get("pubdate", 0)),
        "view": stat.get("view", 0),
        "description": data.get("desc", ""),
        "up_name": owner.get("name", ""),
        "reply": stat.get("reply", 0),
        "danmaku": stat.get("danmaku", 0),
        "up_follower_count": get_up_follower_count(mid, cookie),
    }

    video_dir = get_video_dir(data)
    video_dir.mkdir(parents=True, exist_ok=True)
    output_path = video_dir / "video_info.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"视频信息已保存：{output_path}")
    return output_path


def main():
    ensure_login()
    crawl_video_info()


if __name__ == "__main__":
    main()
