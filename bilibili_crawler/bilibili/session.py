"""采集会话：一次运行共享的登录态和视频上下文。

cookie、WBI 密钥、视频信息和输出目录都按需获取并缓存，避免同一个
视频的多个采集任务重复读盘、重复请求。
"""

from bilibili_api import (
    get_up_follower_count,
    get_video_info,
    get_wbi_mixin_key,
)
from config import VIDEO_OUTPUT_DIR
from crawler_common import safe_filename
from login import get_cookie_header, load_state


def get_video_dir(video_info):
    """生成视频输出目录：`video/{BV号}_{UP主}/`。"""
    up_name = safe_filename(
        video_info.get("owner", {}).get("name") or "unknown"
    )
    bvid = safe_filename(video_info.get("bvid") or "unknown")
    return VIDEO_OUTPUT_DIR / f"{bvid}_{up_name}"


class Session:
    """共享登录态；`cookie` 和 `mixin_key` 只获取一次。"""

    def __init__(self, state=None):
        self._state = state  # 登录状态字典；None 表示还没读 bilibili_state.json
        self._cookie = None  # 缓存拼好的 Cookie 请求头
        self._mixin_key = None  # 缓存 WBI 签名密钥

    @property
    def cookie(self):
        # 第一次访问才读登录状态并拼 Cookie，之后直接用缓存
        if self._cookie is None:
            if self._state is None:
                self._state = load_state()

            self._cookie = get_cookie_header(self._state)

        return self._cookie

    @property
    def mixin_key(self):
        # 第一次访问才请求 nav 接口计算密钥，之后直接用缓存
        if self._mixin_key is None:
            self._mixin_key = get_wbi_mixin_key(self.cookie)

        return self._mixin_key


class VideoSession(Session):
    """单个视频的上下文；视频信息和输出目录只获取一次。

    自己维护的属性：
        bvid: 当前视频的 BV 号。
        video_info: 视频主体信息，首次访问时请求并缓存。
        up_follower_count: UP 主粉丝数，首次访问时请求并缓存。
        video_dir: 视频输出目录，首次访问时计算并缓存。
        page_count: 分 P 总数，等价于 len(pages())。

    方法：
        pages(page_range=None): 返回分 P 列表；传 [START, END] 时只保留
            落在该范围内的分 P。

    继承自 Session：
        cookie: 请求用的 Cookie 头，首次访问时加载并缓存。
        mixin_key: WBI 签名密钥，首次访问时计算并缓存。
    """

    def __init__(self, bvid, state=None):
        super().__init__(state)  # 初始化父类的 _state、_cookie、_mixin_key
        self.bvid = bvid
        self._video_info = None
        self._up_follower_count = None
        self._video_dir = None

    @property
    def video_info(self):
        """视频主体信息，为空时直接报错。"""
        if self._video_info is None:
            self._video_info = get_video_info(
                self.bvid,
                self.cookie,
            )

        if not self._video_info:
            raise RuntimeError(
                f"没有取到视频信息：{self.bvid}，接口返回为空,BV号可能不存在"
            )

        return self._video_info

    @property
    def up_follower_count(self):
        """UP 主粉丝数。"""
        if self._up_follower_count is None:
            owner = self.video_info.get("owner") or {}  # 视频信息里的 UP 主信息
            mid = owner.get("mid")

            if mid:
                self._up_follower_count = get_up_follower_count(
                    mid,
                    self.cookie,
                )

        return self._up_follower_count

    @property
    def video_dir(self):
        # 目录名依赖视频标题和 UP 主，只计算一次
        if self._video_dir is None:
            self._video_dir = get_video_dir(self.video_info)

        return self._video_dir

    def pages(self, page_range=None):
        """返回该视频的分 P 列表，可选按 [START, END] 过滤。"""
        pages = self.video_info.get("pages", [])  # 接口返回的分 P 列表

        if not pages:
            raise RuntimeError(f"没有找到视频分 P：{self.bvid}")

        # 不传范围时返回全部分 P
        if page_range is None:
            return pages

        # 范围必须是两个整数，且满足 1 <= START <= END
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

        # 按分 P 的 page 字段过滤，只保留落在 [start, end] 内的项
        selected = [page for page in pages if start <= page.get("page", 0) <= end]

        if not selected:
            raise RuntimeError(f"视频 {self.bvid} 没有分 P {start}-{end}")

        return selected

    @property
    def page_count(self):
        """分 P 总数。"""
        return len(self.pages())  # 等价于 len(session.pages())


if __name__ == "__main__":
    # s = Session()
    # print("cookie:", s.cookie)
    # print("mixin_key:", s.mixin_key)

    s = VideoSession("BV1q8pA6fEAF")
    info = s.video_info
    pages = s.pages([1, 10])
    print("pages", pages)
    # print("标题：", info.get("title"))
    # print("UP 主：", info.get("owner", {}).get("name"))
    # print("输出目录：", s.video_dir)
    # print("分 P 数量：", s.page_count)
