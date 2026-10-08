"""采集会话：一次运行共享的登录态和视频上下文。

cookie、WBI 密钥、视频信息和输出目录都按需获取并缓存，避免同一个
视频的多个采集任务重复读盘、重复请求。
"""

from bilibili_api import (
    get_video_detail,
    get_wbi_mixin_key,
)
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
        self._video_detail = None  # 详情原始数据缓存，含 View、Card 等
        self._video_dir = None  # 输出目录缓存，首次访问 video_dir 时计算并写入

    @property
    def video_detail(self):
        """视频详情原始数据，含 View、Card、Reply、Related 等字段。"""
        if self._video_detail is None:
            self._video_detail = get_video_detail(
                self.bvid,
                self.cookie,
                self.mixin_key,
            )

        return self._video_detail

    @property
    def video_info(self):
        """视频主体信息（View 字段），为空时直接报错。"""
        info = self.video_detail.get("View", {})

        if not info:
            raise RuntimeError(
                f"没有取到视频信息：{self.bvid}，接口返回为空,BV号可能不存在"
            )

        return info

    @property
    def up_follower_count(self):
        """UP 主粉丝数，取详情 Card 里的 follower。"""
        return (self.video_detail.get("Card") or {}).get("follower")

    @property
    def video_dir(self):
        if self._video_dir is None:
            self._video_dir = get_video_dir(self.video_info)

        return self._video_dir

    def pages(self, page_range=None):
        """返回该视频的分 P 列表，可选按 [START, END] 过滤。"""
        pages = self.video_info.get("pages", [])

        if not pages:
            raise RuntimeError(f"没有找到视频分 P：{self.bvid}")

        if page_range is None:
            return pages

        try:
            start, end = page_range
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"page_range 应为 [START, END] 两个值，收到：{page_range!r}"
            ) from exc

        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError(f"page_range 的两个值必须是整数，收到：{page_range!r}")

        if start < 1 or end < start:
            raise ValueError(
                f"页码范围必须满足 1 <= START <= END，收到：{page_range!r}"
            )

        selected = [page for page in pages if start <= page.get("page", 0) <= end]

        if not selected:
            raise RuntimeError(f"视频 {self.bvid} 没有分 P {start}-{end}")

        return selected

    @property
    def page_count(self):
        """分 P 总数。"""
        return len(self.pages())


if __name__ == "__main__":
    # s = Session()
    # print("cookie:", s.cookie)
    # print("mixin_key:", s.mixin_key)

    s = VideoSession("BV1xx411c7mD")
    info = s.video_info
    pages = s.pages()
    print("pages", pages)
    print("标题：", info.get("title"))
    print("UP 主：", info.get("owner", {}).get("name"))
    print("输出目录：", s.video_dir)
    print("分 P 数量：", s.page_count)
