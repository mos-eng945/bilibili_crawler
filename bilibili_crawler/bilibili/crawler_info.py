"""Bilibili 视频信息采集。"""

from config import DEFAULT_BVID
from crawler_common import (
    format_published_at,
    normalize_url,
    write_json,
    zone_name,
)
from login import ensure_login
from session import VideoSession


class VideoInfoCrawler:
    """采集视频概览和 UP 主粉丝数，写入 `video_info.json`。"""

    def __init__(self, session):
        self.session = session

    def run(self):
        data = self.session.video_info
        stat = data.get("stat", {})
        owner = data.get("owner", {})
        pages = data.get("pages") or []

        result = {
            # 身份：脱离文件夹也能知道是哪条视频，也方便跟搜索/UP 表关联
            "bvid": data.get("bvid", ""),
            "aid": data.get("aid", 0),
            "mid": owner.get("mid", 0),
            # 内容
            "title": data.get("title", ""),
            "description": data.get("desc", ""),
            "cover_url": normalize_url(data.get("pic", "")),
            "published_at": format_published_at(data.get("pubdate", 0)),
            "created_at": format_published_at(data.get("ctime", 0)),
            "duration_seconds": data.get("duration", 0),
            "videos": data.get("videos", 0),
            # 分区：接口只给编号，名字查官方分区表
            "tid": data.get("tid", 0),
            "partition": zone_name(data.get("tid")),
            # UP 主
            "up_name": owner.get("name", ""),
            "up_face": owner.get("face", ""),
            "up_follower_count": self.session.up_follower_count,
            # 统计
            "view": stat.get("view", 0),
            "like": stat.get("like", 0),
            "coin": stat.get("coin", 0),
            "favorite": stat.get("favorite", 0),
            "reply": stat.get("reply", 0),
            "share": stat.get("share", 0),
            "danmaku": stat.get("danmaku", 0),
            # 分 P：只留弹幕/字幕要用到的字段
            "pages": [
                {
                    "page": page.get("page", 0),
                    "cid": page.get("cid", 0),
                    "part": page.get("part", ""),
                    "duration": page.get("duration", 0),
                }
                for page in pages
            ],
        }

        video_dir = self.session.video_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / "video_info.json"

        write_json(output_path, result)

        print(f"视频信息已保存：{output_path}")
        return output_path


def main():
    state = ensure_login()
    VideoInfoCrawler(VideoSession(DEFAULT_BVID, state)).run()


if __name__ == "__main__":
    main()
