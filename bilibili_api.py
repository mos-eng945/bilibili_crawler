"""Bilibili 公共接口、WBI 签名和输出路径工具。"""

import hashlib
import http.client
import json
import threading
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

from login import get_cookie_header, launch_browser, load_state

API_BASE = "https://api.bilibili.com"
USER_AGENT = "Mozilla/5.0"
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_RETRY_ATTEMPTS = 2
_THREAD_LOCAL = threading.local()

# Bilibili WBI 签名使用的字符重排表
MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


def _close_thread_connection():
    """关闭当前线程缓存的 HTTP 连接。"""
    # _THREAD_LOCAL 是 threading.local()，每个线程各存一份 connection。
    # 可能还没存过，所以用 getattr 取，取不到按 None 处理。
    connection = getattr(_THREAD_LOCAL, "connection", None)

    if connection is not None:
        connection.close()  # 断开这条 HTTP 连接

    # 清空缓存，表示当前线程暂时没有可复用的连接
    _THREAD_LOCAL.connection = None


def _get_thread_connection(parsed_url):
    """按线程复用 HTTP/HTTPS 连接。"""
    connection = getattr(_THREAD_LOCAL, "connection", None)

    # 没有可复用连接时新建一条，按 https/http 选择连接类型。
    if connection is None:
        if parsed_url.scheme == "https":
            connection_class = http.client.HTTPSConnection
        else:
            connection_class = http.client.HTTPConnection

        connection = connection_class(
            parsed_url.hostname,
            parsed_url.port,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _THREAD_LOCAL.connection = connection  # 存起来，供下次请求复用

    return connection


def _request(url, cookie, accept="application/json, text/plain, */*"):
    """请求 Bilibili 接口，返回 (HTTP 状态码, 原始响应字节)。"""
    parsed_url = urllib.parse.urlsplit(url)
    path = parsed_url.path or "/"

    if parsed_url.query:
        path = f"{path}?{parsed_url.query}"

    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Accept": accept,
        "Connection": "keep-alive",  # 不要断开连接
    }

    for attempt in range(1, REQUEST_RETRY_ATTEMPTS + 1):
        connection = _get_thread_connection(parsed_url)

        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            body = response.read()
            status = response.status
        except (OSError, http.client.HTTPException) as exc:
            _close_thread_connection()

            if attempt == REQUEST_RETRY_ATTEMPTS:
                raise RuntimeError(f"请求失败：{url}") from exc

            continue

        if status >= 400:
            error_body = body.decode("utf-8", errors="replace")
            raise RuntimeError(f"请求失败：HTTP {status}\n{error_body}")

        return status, body

    raise RuntimeError(f"请求失败：{url}")


def request_json(url, cookie) -> dict:  # pyright: ignore[reportReturnType]
    """请求 Bilibili JSON 接口，复用连接并检查业务错误码。"""
    _, body = _request(url, cookie)

    try:
        data = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        _close_thread_connection()
        raise RuntimeError(f"请求或解析失败：{url}") from exc

    if data.get("code") != 0:
        raise RuntimeError(
            f"Bilibili 接口返回错误：code={data.get('code')} "
            f"message={data.get('message')}"
        )

    return data.get("data", {})


def request_bytes(url, cookie, accept="*/*"):
    """请求二进制接口，返回原始响应字节；HTTP 304 视为无数据。"""
    status, body = _request(url, cookie, accept=accept)

    if status == 304:
        return b""

    return body


def get_wbi_mixin_key(cookie):
    """生成mixin_key，用于 WBI 签名。"""
    nav = request_json(f"{API_BASE}/x/web-interface/nav", cookie)
    img_url = nav.get("wbi_img", {}).get("img_url", "")
    sub_url = nav.get("wbi_img", {}).get("sub_url", "")
    # img_url = "https://i0.hdslb.com/bfs/wbi/abc123.png"
    # path()获得一个path对象  urllib.parse.urlparse(img_url).path解析url并获得路径部分/bfs/wbi/abc123.png     path对象的stem属性获得文件名不带后缀 abc123
    img_key = Path(urllib.parse.urlparse(img_url).path).stem
    sub_key = Path(urllib.parse.urlparse(sub_url).path).stem

    if not img_key or not sub_key:
        raise RuntimeError("无法取得 WBI 密钥，登录状态可能无效")

    raw_key = img_key + sub_key
    # 用重排表获得mixin_key,然后取前32位
    return "".join(raw_key[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def sign_wbi_params(params, mixin_key):
    """生成 WBI 签名。"""
    signed_params = {**params, "wts": int(time.time())}
    query = urllib.parse.urlencode(sorted(signed_params.items()))
    w_rid = hashlib.md5(f"{query}{mixin_key}".encode()).hexdigest()
    return f"{query}&w_rid={w_rid}"


def build_url(path, params):
    """把接口路径和参数拼成可直接访问的完整 URL。"""
    query = urllib.parse.urlencode(params)
    return f"{API_BASE}{path}?{query}"


def build_wbi_url(path, params, mixin_key):
    """把需要 WBI 签名的接口拼成可直接访问的完整 URL。"""
    return f"{API_BASE}{path}?{sign_wbi_params(params, mixin_key)}"


def request_wbi_json(path, params, cookie, mixin_key):
    """请求需要 WBI 签名的 JSON 接口。"""
    return request_json(build_wbi_url(path, params, mixin_key), cookie)


def get_video_info(bvid, cookie):
    """
    取得视频的详细信息（轻量接口）。

    参数：
        bvid: 视频 BV 号，例如 "BV1UT42167xb"。
        cookie: 已登录的请求 Cookie 头，通常来自 Session.cookie。

    返回：
        接口 data 字段的字典，常用字段包括：
        - bvid / aid: 视频 BV 号和 av 号
        - title / desc: 标题和简介
        - pubdate / duration: 发布时间戳(秒)和视频时长(秒)
        - owner: UP 主信息，含 mid、name、face
        - stat: 统计数据，含 view、like、coin、favorite、
          reply、danmaku、share
        - pages: 分 P 列表，每项含 page、cid、part、duration
    """

    # data: 接口返回的顶层数据
    # ├── bvid: 当前视频的 BV 号
    # ├── title: 当前视频的标题
    # ├── owner: 当前视频的 UP 主信息
    # ├── stat: 当前视频的统计数据
    # ├── pages: 当前视频自己的分 P 列表
    # └── ugc_season: 当前视频所属的合集信息
    #     └── sections: 合集下的分区列表
    #         └── episodes: 分区下的视频列表
    #             ├── bvid: 合集内某个视频的 BV 号
    #             ├── pages: 该视频自己的分 P 列表
    #             ├── bvid: 合集内下一个视频的 BV 号
    #             ├── pages: 下一个视频自己的分 P 列表
    #             └── ...: 继续包含后续视频
    query = urllib.parse.urlencode({"bvid": bvid})  # 把字典变成 URL 参数 bvid=BV1
    return request_json(f"{API_BASE}/x/web-interface/view?{query}", cookie)


def get_video_pages(bvid, cookie):
    """取得视频的所有分 P。"""
    data = get_video_info(bvid, cookie)

    return data.get("pages", [])


def get_up_follower_count(mid, cookie):
    """取得 UP 主的粉丝数。"""
    query = urllib.parse.urlencode({"vmid": mid})
    data = request_json(f"{API_BASE}/x/relation/stat?{query}", cookie)

    return data.get("follower", 0)


def search_videos(keyword, cookie, mixin_key, page=1, page_size=50):
    """按关键词搜索视频。"""
    keyword = keyword.strip()

    if not keyword:
        raise ValueError("搜索关键词不能为空")

    # data: 接口返回的顶层数据
    # ├── seid: 本次搜索的会话 ID
    # ├── page: 当前页码
    # ├── pagesize: 每页结果数
    # ├── numResults: 结果总数
    # ├── numPages: 总页数
    # ├── suggest_keyword: 推荐搜索词
    # ├── rqt_type: 请求类型（search）
    # ├── exp_list: 命中的实验分组
    # ├── is_hit_web_inf: 是否命中网页信息
    # ├── egg_hit: 彩蛋命中标记
    # ├── result: 视频结果列表
    # │   └── []: 单个视频
    # │       ├── type: 结果类型（video）
    # │       ├── id / aid: 视频 AV 号
    # │       ├── bvid: 视频 BV 号
    # │       ├── title: 标题，关键词带 <em> 高亮标签
    # │       ├── description: 视频简介
    # │       ├── author / mid / upic: UP 主昵称、UID、头像
    # │       ├── typeid / typename: 分区编号和分区名
    # │       ├── arcurl: 视频播放页地址
    # │       ├── pic: 视频封面
    # │       ├── tag: 标签，逗号分隔
    # │       ├── play / danmaku / like / review / favorites: 播放、弹幕、点赞、评论、收藏数
    # │       ├── duration: 时长，格式 mm:ss
    # │       ├── pubdate / senddate: 发布时间和入库时间
    # │       ├── hit_columns: 关键词命中的字段
    # │       └── ...: 直播、付费、角标等其余字段
    # ├── show_column: 是否显示列表面板
    # ├── in_black_key: 是否命中黑名单
    # ├── in_white_key: 是否命中白名单
    # └── next: 下一页页码
    data = request_wbi_json(
        "/x/web-interface/wbi/search/type",
        {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
        },
        cookie,
        mixin_key,
    )

    # 风控会返回 code=0 但没有 result，只给一个 v_voucher 挑战
    if data.get("v_voucher") and not data.get("result"):
        raise RuntimeError("搜索触发 Bilibili 风控（v_voucher），请降低并发后重试")

    return data


def get_user_videos(
    mid,
    cookie,
    mixin_key,
    page=1,
    page_size=50,
    order="pubdate",
):
    """按 UP 主 MID 分页取得公开视频。"""
    try:
        mid = int(mid)
    except (TypeError, ValueError) as exc:
        raise ValueError("UP 主 MID 必须是数字") from exc

    if mid <= 0:
        raise ValueError("UP 主 MID 必须大于 0")

    # data: 接口返回的顶层数据
    # ├── list: UP 主空间内容
    # │   ├── vlist: 视频列表
    # │   │   └── []: 单个视频
    # │   │       ├── bvid / aid: 视频 BV 号和 AV 号
    # │   │       ├── title: 视频标题
    # │   │       ├── author / mid: UP 主昵称和 UID
    # │   │       ├── created: 发布时间戳
    # │   │       ├── length: 时长，格式 mm:ss
    # │   │       ├── pic: 视频封面
    # │   │       ├── description: 视频简介
    # │   │       ├── play / comment / video_review: 播放、评论、弹幕数
    # │   │       ├── review: 点评数，通常为 0
    # │   │       ├── typeid: 分区编号
    # │   │       ├── copyright: 版权标记，1 自制 2 转载
    # │   │       ├── is_union_video / is_live_playback / is_lesson_video: 联合投稿、直播回放、课程视频标记
    # │   │       └── ...: 充电、跳转、属性等其余字段
    # │   ├── tlist: 按分区聚合的投稿数量
    # │   │   └── {tid}: 分区统计
    # │   │       ├── tid: 分区编号
    # │   │       ├── name: 分区名
    # │   │       └── count: 该分区视频数
    # │   └── slist: 合集/系列列表，无合集时为空
    # ├── page: 分页信息
    # │   ├── pn: 当前页码
    # │   ├── ps: 每页数量
    # │   └── count: 该 UP 主公开视频总数
    # ├── episodic_button: 合集播放入口
    # │   ├── text: 按钮文字（如“播放全部”）
    # │   └── uri: 播放列表地址
    # ├── is_risk: 是否触发风控
    # ├── gaia_res_type: 风控类型
    # └── gaia_data: 风控附加数据
    return request_wbi_json(
        "/x/space/wbi/arc/search",
        {
            "mid": mid,
            "pn": page,
            "ps": page_size,
            # order: pubdate 最新发布 / click 最多播放 / stow 最多收藏
            "order": order,
        },
        cookie,
        mixin_key,
    )


def get_hot_search(cookie, limit=10):
    """取得 Bilibili 搜索热搜列表。"""
    limit = min(max(1, int(limit)), 50)
    query = urllib.parse.urlencode({"limit": limit})
    data = request_json(
        f"{API_BASE}/x/web-interface/search/square?{query}",
        cookie,
    )

    # data: 接口返回的顶层数据
    # └── trending: 热搜榜单
    #     ├── title: 榜单标题（bilibili热搜）
    #     ├── trackid: 榜单追踪 ID
    #     ├── list: 热搜词列表
    #     │   └── []: 单个热搜词
    #     │       ├── keyword: 搜索关键词
    #     │       ├── show_name: 展示名称
    #     │       ├── icon: 右侧图标地址
    #     │       ├── uri: 点击跳转地址
    #     │       ├── goto: 跳转类型
    #     │       └── heat_score: 热度值
    #     └── top_list: 置顶热搜列表
    #         └── []: 置顶条目，字段同 list 并附带 pos、hot_id 等
    return (data.get("trending") or {}).get("list") or []


def _extract_subtitle_tracks(data):
    """从播放器响应中取得字幕轨道。"""
    subtitle = data.get("subtitle", {})
    return subtitle.get("subtitles") or subtitle.get("list") or []


def get_player_subtitles(bvid, cid, cookie, mixin_key):
    """取得指定分 P 的字幕列表。"""
    data = request_wbi_json(
        "/x/player/wbi/v2",
        {"bvid": bvid, "cid": cid},
        cookie,
        mixin_key,
    )

    return _extract_subtitle_tracks(data)


# 评论接口的页面位置编号，仅用于埋点，不影响数据过滤
COMMENT_WEB_LOCATION = 1315875


def fetch_comment_page(oid, cursor, cookie, mixin_key, mode, page_size):
    """请求一页一级评论（WBI 游标分页）。

    参数：
        oid: 视频 aid。
        cursor: 上一页响应里的 data["cursor"]，首页传空字典。
        mode: 2 时间顺序，3 热门。
        page_size: 每页条数。
    """
    next_offset = (cursor.get("pagination_reply") or {}).get("next_offset") or ""
    params = {
        "oid": oid,
        "type": 1,
        "mode": mode,
        "next": cursor.get("next", 0),
        "ps": page_size,
        "pagination_str": json.dumps(
            {"offset": next_offset},
            separators=(",", ":"),
        ),
        "plat": 1,  # 网页端发送
        "web_location": COMMENT_WEB_LOCATION,
    }

    return request_wbi_json("/x/v2/reply/wbi/main", params, cookie, mixin_key)


# 弹幕分段接口每段覆盖 360 秒（6 分钟），segment_index 从 1 开始
DANMAKU_SEGMENT_SECONDS = 360
DANMAKU_SEGMENT_MS = DANMAKU_SEGMENT_SECONDS * 1000
# 播放器弹幕模块的页面位置编号，仅用于埋点，不影响数据过滤
DANMAKU_WEB_LOCATION = 1315873


def fetch_danmaku_segment(oid, aid, segment_index, cookie, mixin_key):
    """请求一个弹幕分段，返回 Protobuf 原始字节。

    使用播放器当前的 `/x/v2/dm/wbi/web/seg.so` 接口：
        oid: 分 P 的 cid。
        aid: 视频 aid，对应接口的 pid。
        segment_index: 第几段，从 1 开始。
        ps / pe: 该段的起止时间，单位毫秒，接口会按这个窗口过滤弹幕。

    分段越界时接口返回 HTTP 304，这里统一按空字节处理。
    """
    params = {
        "type": 1,
        "oid": oid,
        "pid": aid,
        "segment_index": segment_index,
        "pull_mode": 1,
        "ps": (segment_index - 1) * DANMAKU_SEGMENT_MS,
        "pe": segment_index * DANMAKU_SEGMENT_MS,
        "web_location": DANMAKU_WEB_LOCATION,
    }

    return request_bytes(
        build_wbi_url("/x/v2/dm/wbi/web/seg.so", params, mixin_key), cookie
    )


def open_in_browser(url=None, state=None, headless=False):
    if state is None:
        state = load_state()

    if not url:
        raise ValueError(f"URL 不能为空，请先调用 build_url(...)")

    print("浏览器前往:", url)

    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=headless)
        context = (
            browser.new_context(storage_state=state) if state else browser.new_context()
        )
        page = context.new_page()

        page.goto(url)

        input("按回车关闭浏览器...")
        browser.close()


if __name__ == "__main__":
    # print("获取 WBI 混合密钥:" + get_wbi_mixin_key(get_cookie_header(load_state())))

    # print(
    #     "签名参数:",
    #     sign_wbi_params(
    #         {"bvid": "BV1UT42167xb", "page": 1},
    #         get_wbi_mixin_key(get_cookie_header(load_state())),
    #     ),
    # )

    # open_in_browser(build_url("/x/web-interface/view", {"bvid": "BV1UT42167xb"}))

    # open_in_browser(build_url("/x/relation/stat", {"vmid": "2043250564"}))

    # open_in_browser(
    #     build_wbi_url(
    #         "/x/space/wbi/arc/search",
    #         {
    #             "mid": "2043250564",
    #             "order": "click",
    #             "ps": 50,
    #         },
    #         get_wbi_mixin_key(get_cookie_header(load_state())),
    #     )
    # )

    # open_in_browser(
    #     build_url(
    #         "/x/web-interface/search/square",
    #         {
    #             "limit": 50,
    #         },
    #     )
    # )
    # open_in_browser(
    #     build_wbi_url(
    #         "/x/web-interface/wbi/search/type",
    #         {
    #             "search_type": "video",
    #             "keyword": "python",
    #             "page": 1,
    #             "page_size": 50,
    #         },
    #         get_wbi_mixin_key(get_cookie_header(load_state())),
    #     )
    # )

    open_in_browser(
        build_wbi_url(
            "/x/v2/reply/wbi/main",
            {
                "oid": "1706416465",
                "offset": "CAESEDE4MzQ2MjI3MDAyMTE2MDgaADIDCLQb",
                "type": 1,
                "mode": 2,
                "ps": 30,
            },
            get_wbi_mixin_key(get_cookie_header(load_state())),
        )
    )
