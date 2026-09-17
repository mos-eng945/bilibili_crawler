"""
Bilibili 字幕下载器。

整体思路：
1. 从登录状态生成请求 Cookie。
2. 通过 nav 接口取得 WBI 密钥，并为接口参数生成签名。
3. 获取视频分 P 和可用字幕列表。
4. 下载字幕 JSON，同时转换成 SRT 文本并保存到视频目录。
"""

import argparse
import json
import urllib.request

from bilibili_api import (
    USER_AGENT,
    get_cookie_header,
    get_player_subtitles,
    get_video_info,
    get_wbi_mixin_key,
)
from login import ensure_login
from main import DEFAULT_BVID
from video_paths import get_video_dir, safe_filename


def download_subtitle_json(url, cookie):
    """下载字幕正文 JSON。"""
    if url.startswith("//"):
        url = f"https:{url}"

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
            return json.load(response)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"字幕文件下载失败：{url}") from exc


def format_srt_timestamp(seconds):
    """把秒数转换成 SRT 时间格式。"""
    total_milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def subtitle_to_srt(subtitle):
    """把 Bilibili 字幕 JSON 转换成 SRT 文本。"""
    blocks = []

    for index, item in enumerate(subtitle.get("body", []), start=1):
        content = str(item.get("content", "")).replace("\r\n", "\n").strip()
        blocks.append(
            "\n".join(
                [
                    str(index),
                    (
                        f"{format_srt_timestamp(item.get('from', 0))} --> "
                        f"{format_srt_timestamp(item.get('to', 0))}"
                    ),
                    content,
                ]
            )
        )

    return "\n\n".join(blocks).strip() + "\n"


def save_subtitle(
    video_dir,
    bvid,
    cid,
    page_number,
    part,
    subtitle_item,
    subtitle_data,
):
    """保存字幕 JSON，并同时生成 SRT。"""
    language = safe_filename(subtitle_item.get("lan") or "unknown")
    base_name = f"subtitle_{bvid}_p{page_number}_{language}"

    video_dir.mkdir(parents=True, exist_ok=True)

    json_path = video_dir / f"{base_name}.json"
    srt_path = video_dir / f"{base_name}.srt"

    payload = {
        "bvid": bvid,
        "cid": cid,
        "page": page_number,
        "part": part,
        "language": subtitle_item.get("lan"),
        "language_name": subtitle_item.get("lan_doc"),
        "subtitle": subtitle_data,
    }

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    with open(srt_path, "w", encoding="utf-8") as file:
        file.write(subtitle_to_srt(subtitle_data))

    return json_path, srt_path


def crawl_subtitles(
    bvid=DEFAULT_BVID,
    page_number=None,
    language=None,
):
    """下载视频全部或指定分 P 的字幕。"""
    cookie = get_cookie_header()
    mixin_key = get_wbi_mixin_key(cookie)
    video_info = get_video_info(bvid, cookie)
    pages = video_info.get("pages", [])
    video_dir = get_video_dir(video_info)

    if not pages:
        raise RuntimeError(f"没有找到视频分 P：{bvid}")

    if page_number is not None:
        pages = [page for page in pages if page.get("page") == page_number]

        if not pages:
            raise RuntimeError(f"视频 {bvid} 没有第 {page_number} 个分 P")

    downloaded = 0

    for page in pages:
        current_page = page.get("page", 1)
        cid = page.get("cid")
        part = page.get("part", "")

        if not cid:
            print(f"跳过 P{current_page}：没有 cid")
            continue

        subtitle_items = get_player_subtitles(bvid, cid, cookie, mixin_key)

        if language:
            subtitle_items = [
                item for item in subtitle_items if item.get("lan") == language
            ]

        if not subtitle_items:
            print(f"P{current_page} 没有找到可下载字幕")
            continue

        print(f"P{current_page} 找到 {len(subtitle_items)} 条字幕")

        for subtitle_item in subtitle_items:
            subtitle_url = subtitle_item.get("subtitle_url")

            if not subtitle_url:
                print(f"跳过 {subtitle_item.get('lan')}：没有字幕地址")
                continue

            subtitle_data = download_subtitle_json(subtitle_url, cookie)
            json_path, srt_path = save_subtitle(
                video_dir,
                bvid,
                cid,
                current_page,
                part,
                subtitle_item,
                subtitle_data,
            )

            downloaded += 1
            print(f"已保存：{json_path.name}")
            print(f"已保存：{srt_path.name}")

    print(f"下载完成，共保存 {downloaded} 条字幕")


def main():
    parser = argparse.ArgumentParser(description="下载 Bilibili 字幕")
    parser.add_argument(
        "bvid",
        nargs="?",
        default=DEFAULT_BVID,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="只采集指定分 P",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="只采集指定语言，例如 zh-CN 或 ai-zh",
    )
    args = parser.parse_args()

    ensure_login()
    crawl_subtitles(
        args.bvid,
        page_number=args.page,
        language=args.language,
    )


if __name__ == "__main__":
    main()
