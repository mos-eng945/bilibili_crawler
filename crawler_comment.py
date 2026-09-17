"""Bilibili 一级评论下载器。"""

import argparse
import csv
import json
import re
import time

from bilibili_api import (
    get_cookie_header,
    get_video_info,
    get_wbi_mixin_key,
    request_wbi_json,
)
from login import ensure_login
from main import DEFAULT_BVID
from video_paths import get_video_dir

COMMENT_COLUMNS = [
    "rpid",
    "mid",
    "user_name",
    "user_level",
    "message",
    "ctime",
    "like",
    "reply_count",
    "state",
    "image_urls",
]
COMMENT_MODE_TIME = 2
COMMENT_PAGE_SIZE = 30
COMMENT_WEB_LOCATION = 1315875
COMMENT_PROGRESS_PAGE_INTERVAL = 10
COMMENT_RETRY_ATTEMPTS = 3
COMMENT_RETRY_DELAY_SECONDS = 1


def parse_image_urls(content):
    """提取评论图片地址，不下载图片。"""
    urls = []

    for item in content.get("pictures") or []:
        url = item.get("img_src") or ""

        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("http://"):
            url = f"https://{url[7:]}"

        if url:
            urls.append(url)

    return urls


def normalize_text(value):
    """把评论文本规范成适合 CSV 的单行内容。"""
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n+", r"\\n", text)
    return text.strip()


def parse_comment(comment):
    """把评论接口数据转换成轻量记录。"""
    member = comment.get("member") or {}
    level_info = member.get("level_info") or {}
    content = comment.get("content") or {}

    return {
        "rpid": comment.get("rpid"),
        "mid": comment.get("mid"),
        "user_name": normalize_text(member.get("uname", "")),
        "user_level": level_info.get("current_level", 0),
        "message": normalize_text(content.get("message", "")),
        "ctime": comment.get("ctime", 0),
        "like": comment.get("like", 0),
        "reply_count": comment.get("count", 0),
        "state": comment.get("state", 0),
        "image_urls": parse_image_urls(content),
    }


def request_comment_page(oid, page_cursor, cookie, mixin_key):
    """使用游标请求一页一级评论。"""
    params = {
        "oid": oid,
        "type": 1,
        "mode": COMMENT_MODE_TIME,
        "next": page_cursor.get("next", 0),
        "ps": COMMENT_PAGE_SIZE,
        "pagination_str": json.dumps(
            {"offset": page_cursor.get("offset", "")},
            separators=(",", ":"),
        ),
        "plat": 1,
        "web_location": COMMENT_WEB_LOCATION,
    }

    return request_wbi_json(
        "/x/v2/reply/wbi/main",
        params,
        cookie,
        mixin_key,
    )


def request_comment_page_with_retry(oid, page_cursor, cookie, mixin_key):
    """请求评论页，并在失败时短暂重试。"""
    for attempt in range(1, COMMENT_RETRY_ATTEMPTS + 1):
        try:
            return request_comment_page(
                oid,
                page_cursor,
                cookie,
                mixin_key,
            )
        except RuntimeError:
            if attempt == COMMENT_RETRY_ATTEMPTS:
                raise

            time.sleep(COMMENT_RETRY_DELAY_SECONDS)


def extract_page_comments(data, include_top=False):
    """提取当前页的一级评论并转换成轻量记录。"""
    replies = []

    if include_top:
        replies.extend(data.get("top_replies") or [])

    replies.extend(data.get("replies") or [])
    return [parse_comment(comment) for comment in replies]


def crawl_comments(
    bvid=DEFAULT_BVID,
    workers=None,
):
    """采集视频的全部一级评论并保存为 CSV。"""
    if workers is not None:
        print("游标分页需要顺序请求，workers 参数不再生效")

    cookie = get_cookie_header()
    video_info = get_video_info(bvid, cookie)
    oid = video_info.get("aid")

    if not oid:
        raise RuntimeError(f"视频 {bvid} 没有返回 aid")

    mixin_key = get_wbi_mixin_key(cookie)
    comments = []
    seen_rpids = set()
    page_cursor = {}
    page_number = 0
    total_reply_count = 0
    print("开始采集评论，使用 WBI 游标分页")

    while True:
        data = request_comment_page_with_retry(
            oid,
            page_cursor,
            cookie,
            mixin_key,
        )
        page_number += 1
        page_comments = extract_page_comments(
            data,
            include_top=page_number == 1,
        )

        for comment in page_comments:
            rpid = comment["rpid"]

            if rpid in seen_rpids:
                continue

            seen_rpids.add(rpid)
            comments.append(comment)

        cursor = data.get("cursor") or {}
        total_reply_count = cursor.get("all_count") or total_reply_count
        is_end = bool(cursor.get("is_end"))
        next_offset = (
            cursor.get("pagination_reply") or {}
        ).get("next_offset")

        if (
            page_number == 1
            or page_number % COMMENT_PROGRESS_PAGE_INTERVAL == 0
            or is_end
        ):
            print(
                f"已获取第 {page_number} 页，"
                f"一级评论 {len(comments)} 条；"
                f"视频总评论 {total_reply_count} 条（含子评论）"
            )

        if is_end or not next_offset:
            break

        page_cursor = {
            "next": cursor.get("next", 0),
            "offset": next_offset,
        }

    video_dir = get_video_dir(video_info)
    video_dir.mkdir(parents=True, exist_ok=True)
    output_path = video_dir / f"comments_{bvid}.csv"

    with open(output_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COMMENT_COLUMNS)
        writer.writeheader()

        for comment in comments:
            row = {
                **comment,
                "image_urls": "|".join(comment["image_urls"]),
            }
            writer.writerow(row)

    print(
        f"评论已保存：{output_path}，"
        f"共 {len(comments)} 条一级评论；"
        f"视频总评论 {total_reply_count} 条（含子评论）"
    )
    return output_path


def main():
    parser = argparse.ArgumentParser(description="下载 Bilibili 一级评论")
    parser.add_argument(
        "bvid",
        nargs="?",
        default=DEFAULT_BVID,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="兼容旧参数；WBI 游标分页需要顺序请求",
    )
    args = parser.parse_args()

    ensure_login()
    crawl_comments(args.bvid, workers=args.workers)


if __name__ == "__main__":
    main()
