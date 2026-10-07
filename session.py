"""采集会话：一次运行共享的登录态和视频上下文。

cookie、WBI 密钥、视频信息和输出目录都按需获取并缓存，避免同一个
视频的多个采集任务重复读盘、重复请求。
"""

from bilibili_api import get_video_info, get_wbi_mixin_key
from login import get_cookie_header
from output_paths import get_video_dir


class Session:
    """共享登录态；`cookie` 和 `mixin_key` 只获取一次。"""

    def __init__(self):
        self._cookie = None
        self._mixin_key = None

    @property
    def cookie(self):
        if self._cookie is None:
            self._cookie = get_cookie_header()

        return self._cookie

    @property
    def mixin_key(self):
        if self._mixin_key is None:
            self._mixin_key = get_wbi_mixin_key(self.cookie)

        return self._mixin_key


class VideoSession(Session):
    """单个视频的上下文；视频信息和输出目录只获取一次。"""

    def __init__(self, bvid):
        super().__init__()
        self.bvid = bvid
        self._video_info = None
        self._video_dir = None

    @property
    def video_info(self):
        if self._video_info is None:
            info = get_video_info(self.bvid, self.cookie)

            if not info:
                raise RuntimeError(
                    f"没有取到视频信息：{self.bvid}，BV 号可能不存在"
                )

            missing = [
                key
                for key in ("bvid", "title", "owner")
                if not info.get(key)
            ]

            if missing:
                raise RuntimeError(
                    f"视频 {self.bvid} 的返回信息缺少字段："
                    f"{'、'.join(missing)}"
                )

            self._video_info = info

        return self._video_info

    @property
    def video_dir(self):
        if self._video_dir is None:
            self._video_dir = get_video_dir(self.video_info)

        return self._video_dir

    def pages(self, page_range=None):
        """返回该视频的分 P 列表，可选按 START,END 过滤。"""
        pages = self.video_info.get("pages", [])

        if not pages:
            raise RuntimeError(f"没有找到视频分 P：{self.bvid}")

        if page_range is None:
            return pages

        start, end = page_range
        selected = [
            page
            for page in pages
            if start <= page.get("page", 0) <= end
        ]

        if not selected:
            raise RuntimeError(f"视频 {self.bvid} 没有分 P {start}-{end}")

        return selected
