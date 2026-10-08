"""Bilibili 公共接口、WBI 签名和输出路径工具。"""

import hashlib
import http.client
import json
import threading
import time
import urllib.parse
from pathlib import Path

from login import get_cookie_header

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
    connection = getattr(_THREAD_LOCAL, "connection", None)

    if connection is not None:
        connection.close()

    _THREAD_LOCAL.connection = None
    _THREAD_LOCAL.connection_key = None


def _get_thread_connection(parsed_url):
    """按线程复用同一主机的 HTTP/HTTPS 连接。"""
    connection_key = (
        parsed_url.scheme,
        parsed_url.hostname,
        parsed_url.port,
    )
    connection = getattr(_THREAD_LOCAL, "connection", None)

    if (
        connection is not None
        and getattr(_THREAD_LOCAL, "connection_key", None) != connection_key
    ):
        _close_thread_connection()
        connection = None

    if connection is None:
        connection_class = (
            http.client.HTTPSConnection
            if parsed_url.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_class(
            parsed_url.hostname,
            parsed_url.port,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _THREAD_LOCAL.connection = connection
        _THREAD_LOCAL.connection_key = connection_key

    return connection


def request_json(url, cookie):
    """请求 Bilibili JSON 接口，复用连接并检查业务错误码。"""
    parsed_url = urllib.parse.urlsplit(url)
    path = parsed_url.path or "/"

    if parsed_url.query:
        path = f"{path}?{parsed_url.query}"

    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
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
            raise RuntimeError(
                f"请求失败：HTTP {status}\n{error_body}"
            )

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

    raise RuntimeError(f"请求失败：{url}")


def get_wbi_mixin_key(cookie):
    """生成mixin_key，用于 WBI 签名。"""
    nav = request_json(f"{API_BASE}/x/web-interface/nav", cookie)
    img_url = nav.get("wbi_img", {}).get("img_url", "")
    sub_url = nav.get("wbi_img", {}).get("sub_url", "")

    img_key = Path(urllib.parse.urlparse(img_url).path).stem
    sub_key = Path(urllib.parse.urlparse(sub_url).path).stem

    if not img_key or not sub_key:
        raise RuntimeError("无法取得 WBI 密钥，登录状态可能无效")

    raw_key = img_key + sub_key
    return "".join(raw_key[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def sign_wbi_params(params, mixin_key):
    """生成 WBI 签名。"""
    signed_params = {**params, "wts": int(time.time())}
    query = urllib.parse.urlencode(sorted(signed_params.items()))
    w_rid = hashlib.md5(f"{query}{mixin_key}".encode()).hexdigest()
    return f"{query}&w_rid={w_rid}"

# 
def request_wbi_json(path, params, cookie, mixin_key):
    """请求需要 WBI 签名的 JSON 接口。"""
    query = sign_wbi_params(params, mixin_key)
    return request_json(f"{API_BASE}{path}?{query}", cookie)


def get_video_detail(bvid, cookie, mixin_key):
    """
    取得视频详情的原始数据。

    调用前端同款的 `/x/web-interface/wbi/view/detail` 接口（需要 WBI 签名），
    返回 data 的完整字典，包含 View(视频主体)、Card(UP 主卡片)、
    Tags(标签)、Reply(首屏评论)、Related(相关推荐) 等字段。

    参数：
        bvid: 视频 BV 号，例如 "BV1UT42167xb"。
        cookie: 已登录的请求 Cookie 头，通常来自 Session.cookie。
        mixin_key: WBI 签名密钥，通常来自 Session.mixin_key。
    """
    return request_wbi_json(
        "/x/web-interface/wbi/view/detail",
        {
            "bvid": bvid,
            "need_operation_card": 1,
            "web_rm_repeat": 1,
            "need_elec": 1,
            "page_no": 1,
            "p": 1,
        },
        cookie,
        mixin_key,
    )


def get_video_info(bvid, cookie):
    """
    取得视频的详细信息（轻量接口）。

    调用 `/x/web-interface/view`，只返回视频主体数据，响应约 2KB。
    批量拉取（如 UP 主视频列表）用这个，避免详情接口多出约 40 倍的数据；
    需要 Card(UP 主卡片)、Related(相关推荐) 等字段时用 get_video_detail。

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
    query = urllib.parse.urlencode({"bvid": bvid})
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


def search_videos(keyword, cookie, mixin_key, page=1, page_size=20):
    """按关键词搜索视频。"""
    keyword = keyword.strip()

    if not keyword:
        raise ValueError("搜索关键词不能为空")

    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), 50)

    return request_wbi_json(
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


def get_user_videos(
    mid,
    cookie,
    mixin_key,
    page=1,
    page_size=30,
    order="pubdate",
):
    """按 UP 主 MID 分页取得公开视频。"""
    try:
        mid = int(mid)
    except (TypeError, ValueError) as exc:
        raise ValueError("UP 主 MID 必须是数字") from exc

    if mid <= 0:
        raise ValueError("UP 主 MID 必须大于 0")

    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), 50)

    return request_wbi_json(
        "/x/space/wbi/arc/search",
        {
            "mid": mid,
            "pn": page,
            "ps": page_size,
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
