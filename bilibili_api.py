"""Bilibili 公共接口和 WBI 签名工具。"""

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from login import get_cookie_header

API_BASE = "https://api.bilibili.com"
USER_AGENT = "Mozilla/5.0"

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


def request_json(url, cookie):
    """请求 Bilibili JSON 接口，并检查业务错误码。"""
    request = urllib.request.Request(
        url,
        headers={
            "Cookie": cookie,
            "User-Agent": USER_AGENT,
            "Referer": "https://www.bilibili.com/",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"请求失败：HTTP {exc.code}\n{error_body}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"请求或解析失败：{url}") from exc

    if data.get("code") != 0:
        raise RuntimeError(
            f"Bilibili 接口返回错误：code={data.get('code')} "
            f"message={data.get('message')}"
        )

    return data.get("data", {})


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


def request_wbi_json(path, params, cookie, mixin_key):
    """请求需要 WBI 签名的 JSON 接口。"""
    query = sign_wbi_params(params, mixin_key)
    return request_json(f"{API_BASE}{path}?{query}", cookie)


def get_video_info(bvid, cookie):
    """取得视频的详细信息。"""
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
