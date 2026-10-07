"""Bilibili 视频信息采集。"""

from bilibili_api import get_up_follower_count
from config import DEFAULT_BVID
from crawler_common import format_published_at, write_json
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
        mid = owner.get("mid")

        if not mid:
            raise RuntimeError(
                f"视频 {self.session.bvid} 没有返回 UP 主 mid"
            )

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
            "up_follower_count": get_up_follower_count(
                mid,
                self.session.cookie,
            ),
        }

        video_dir = self.session.video_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / "video_info.json"

        write_json(output_path, result)

        print(f"视频信息已保存：{output_path}")
        return output_path


def main():
    ensure_login()
    VideoInfoCrawler(VideoSession(DEFAULT_BVID)).run()


if __name__ == "__main__":
    main()
