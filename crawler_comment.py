"""Bilibili 一级评论下载器。"""

import argparse
import csv
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from bilibili_api import (
    API_BASE,
    get_cookie_header,
    get_video_info,
    request_json,
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
COMMENT_SORT_TIME = 0
COMMENT_PAGE_SIZE = 20
COMMENT_PAGE_WORKERS = 6
COMMENT_PAGE_BATCH_SIZE = 20
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


def request_comment_page(oid, page_number, cookie):
    """请求指定页码的一级评论。"""
    query = urllib.parse.urlencode(
        {
            "type": 1,
            "oid": oid,
            "sort": COMMENT_SORT_TIME,
            "ps": COMMENT_PAGE_SIZE,
            "pn": page_number,
        }
    )

    return request_json(f"{API_BASE}/x/v2/reply?{query}", cookie)


def request_comment_page_with_retry(oid, page_number, cookie):
    """请求评论页，并在失败时短暂重试。"""
    for attempt in range(1, COMMENT_RETRY_ATTEMPTS + 1):
        try:
            return request_comment_page(oid, page_number, cookie)
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


def fetch_page_batch(oid, page_numbers, cookie, workers):
    """并发请求一批连续页码。"""
    results = {}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                request_comment_page_with_retry,
                oid,
                page_number,
                cookie,
            ): page_number
            for page_number in page_numbers
        }

        for future in as_completed(futures):
            page_number = futures[future]
            results[page_number] = future.result()

    return results


def has_comment_page(oid, page_number, cookie):
    """判断指定页码是否还有一级评论。"""
    if page_number < 1:
        return False

    data = request_comment_page_with_retry(oid, page_number, cookie)
    return bool(data.get("replies"))


def crawl_comments(
    bvid=DEFAULT_BVID,
    workers=COMMENT_PAGE_WORKERS,
):
    """并发采集视频的全部一级评论并保存为 CSV。"""
    cookie = get_cookie_header()
    video_info = get_video_info(bvid, cookie)
    oid = video_info.get("aid")

    if not oid:
        raise RuntimeError(f"视频 {bvid} 没有返回 aid")

    worker_count = max(1, workers)
    page_results = {}
    next_page = 1
    finished = False
    print(f"开始并发采集评论，使用 {worker_count} 个请求线程")

    while not finished:
        batch_pages = range(
            next_page,
            next_page + COMMENT_PAGE_BATCH_SIZE,
        )
        batch_data = fetch_page_batch(
            oid,
            batch_pages,
            cookie,
            worker_count,
        )
        page_results.update(
            {
                page_number: extract_page_comments(
                    data,
                    include_top=page_number == 1,
                )
                for page_number, data in batch_data.items()
            }
        )

        empty_pages = [
            page_number
            for page_number, data in batch_data.items()
            if not data.get("replies")
        ]

        if empty_pages:
            first_empty_page = min(empty_pages)

            # 再确认下一页确实为空，避免把临时空页当成结尾。
            next_after_empty = first_empty_page + 1

            if next_after_empty in batch_data:
                finished = not batch_data[next_after_empty].get("replies")
            else:
                finished = not has_comment_page(
                    oid,
                    next_after_empty,
                    cookie,
                )

            if not finished:
                next_page = next_after_empty
                continue
        else:
            next_page += COMMENT_PAGE_BATCH_SIZE

        non_empty_pages = sorted(
            page_number
            for page_number, comments in page_results.items()
            if comments
        )
        completed_count = sum(
            len(page_results[page_number])
            for page_number in non_empty_pages
        )
        print(
            f"已扫描到第 {max(batch_pages)} 页，"
            f"获得 {completed_count} 条一级评论"
        )

    comments = []
    seen_rpids = set()

    for page_number in sorted(page_results):
        for comment in page_results[page_number]:
            rpid = comment["rpid"]

            if rpid in seen_rpids:
                continue

            seen_rpids.add(rpid)
            comments.append(comment)

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

    print(f"评论已保存：{output_path}，共 {len(comments)} 条")
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
        default=COMMENT_PAGE_WORKERS,
        help=f"并发请求数，默认为 {COMMENT_PAGE_WORKERS}",
    )
    args = parser.parse_args()

    ensure_login()
    crawl_comments(args.bvid, workers=args.workers)


if __name__ == "__main__":
    main()
