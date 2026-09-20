"""Bilibili 关键词视频搜索。"""

import csv
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

from bilibili_api import (
    BASE_DIR,
    get_cookie_header,
    get_hot_search,
    get_up_follower_count,
    get_video_info,
    get_wbi_mixin_key,
    safe_filename,
    search_videos,
)

SEARCH_DEFAULT_WORKERS = 3
SEARCH_MAX_WORKERS = 5
SEARCH_RETRY_ATTEMPTS = 3
SEARCH_RETRY_DELAY_SECONDS = 1
CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")
SEARCH_COLUMNS = [
    "bvid",
    "title",
    "published_at",
    "author",
    "mid",
    "like",
    "comment_count",
    "favorite_count",
    "share_count",
    "author_follower_count",
    "play_count",
    "danmaku_count",
]

def clean_html_text(value):
    """移除搜索结果标题中的高亮标签。"""
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return html.unescape(text).strip()


def format_published_at(timestamp):
    """把秒级时间戳转换成中国时区的 ISO 时间。"""
    try:
        return datetime.fromtimestamp(
            int(timestamp),
            tz=CHINA_TIMEZONE,
        ).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def request_with_retry(function, *args, **kwargs):
    """请求失败时短暂等待并重试。"""
    for attempt in range(1, SEARCH_RETRY_ATTEMPTS + 1):
        try:
            return function(*args, **kwargs)
        except RuntimeError:
            if attempt == SEARCH_RETRY_ATTEMPTS:
                raise

            time.sleep(SEARCH_RETRY_DELAY_SECONDS * attempt)


def run_concurrently(function, values, workers, label):
    """并发执行任务，并按输入顺序返回结果。"""
    total = len(values)

    if total == 0:
        return []

    worker_count = min(max(1, int(workers)), total)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = []

        for result in executor.map(function, values):
            results.append(result)
            completed = len(results)
            if completed == total or completed % 5 == 0:
                print(f"{label}进度：{completed}/{total}")

    return results


def fetch_video_info_safely(bvid, cookie):
    """请求视频详情，失败时返回 None。"""
    try:
        return request_with_retry(get_video_info, bvid, cookie)
    except RuntimeError as exc:
        print(f"视频 {bvid} 详情获取失败，使用搜索结果：{exc}")
        return None


def fetch_follower_count_safely(mid, author, cookie):
    """请求作者粉丝数，失败时返回 0。"""
    try:
        return request_with_retry(get_up_follower_count, mid, cookie)
    except RuntimeError as exc:
        print(f"作者 {author or mid} 粉丝数获取失败：{exc}")
        return 0


def parse_search_video(item, video_info=None):
    """把搜索结果和视频详情合并成 CSV 行。"""
    bvid = item.get("bvid", "")
    published_at = format_published_at(item.get("pubdate"))
    search_mid = item.get("mid")
    author = clean_html_text(item.get("author"))
    like = item.get("like", 0)
    comment_count = item.get("review", 0)
    favorite_count = item.get("favorites", 0)
    share_count = 0
    play_count = item.get("play", 0)
    danmaku_count = item.get("video_review", 0)
    mid = search_mid

    if video_info:
        stat = video_info.get("stat") or {}
        owner = video_info.get("owner") or {}

        published_at = format_published_at(
            video_info.get("pubdate") or item.get("pubdate")
        )
        author = owner.get("name") or author
        mid = owner.get("mid") or mid
        like = stat.get("like", like)
        comment_count = stat.get("reply", comment_count)
        favorite_count = stat.get("favorite", favorite_count)
        share_count = stat.get("share", 0)
        play_count = stat.get("view", play_count)
        danmaku_count = stat.get("danmaku", danmaku_count)

    return {
        "bvid": bvid,
        "title": clean_html_text(item.get("title")),
        "published_at": published_at,
        "author": author,
        "mid": mid or "",
        "like": like,
        "comment_count": comment_count,
        "favorite_count": favorite_count,
        "share_count": share_count,
        "author_follower_count": 0,
        "play_count": play_count,
        "danmaku_count": danmaku_count,
    }


def fetch_search_items(
    keyword,
    cookie,
    mixin_key,
    page_numbers,
    page_size,
    workers,
):
    """并发请求搜索页，并按 BV 号去重搜索结果。"""

    def fetch_page(current_page):
        return request_with_retry(
            search_videos,
            keyword,
            cookie,
            mixin_key,
            page=current_page,
            page_size=page_size,
        )

    page_results = run_concurrently(
        fetch_page,
        page_numbers,
        workers,
        "搜索页",
    )
    total_results = 0
    items = []
    seen_bvids = set()

    for data in page_results:
        total_results = data.get("numResults", total_results)

        for item in data.get("result") or []:
            bvid = item.get("bvid", "")

            if not bvid or bvid in seen_bvids:
                continue

            seen_bvids.add(bvid)
            items.append(item)

    return items, total_results


def fetch_search_rows(items, cookie, workers):
    """并发请求视频详情，并生成搜索结果行。"""
    bvids = [item["bvid"] for item in items]
    video_infos = run_concurrently(
        lambda bvid: fetch_video_info_safely(bvid, cookie),
        bvids,
        workers,
        "视频详情",
    )

    return [
        parse_search_video(item, video_info)
        for item, video_info in zip(items, video_infos)
    ]


def fill_author_follower_counts(rows, cookie, workers):
    """按作者 mid 并发补充搜索结果的粉丝数。"""
    mids = list(
        dict.fromkeys(row["mid"] for row in rows if row["mid"])
    )
    author_names = {
        row["mid"]: row["author"] for row in rows if row["mid"]
    }
    follower_counts = run_concurrently(
        lambda mid: fetch_follower_count_safely(
            mid,
            author_names.get(mid, ""),
            cookie,
        ),
        mids,
        workers,
        "作者粉丝数",
    )
    follower_by_mid = dict(zip(mids, follower_counts))

    for row in rows:
        row["author_follower_count"] = follower_by_mid.get(row["mid"], 0)


def _crawl_search_with_context(
    keyword,
    cookie,
    mixin_key,
    output_root=None,
    page=1,
    pages=1,
    page_size=20,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """搜索视频，补齐互动数据并保存为 CSV。"""
    keyword = keyword.strip()

    if not keyword:
        raise ValueError("搜索关键词不能为空")

    page = max(1, int(page))
    pages = max(1, int(pages))
    page_size = min(max(1, int(page_size)), 50)
    workers = min(
        max(1, int(workers)),
        SEARCH_MAX_WORKERS,
    )

    page_numbers = list(range(page, page + pages))
    items, total_results = fetch_search_items(
        keyword,
        cookie,
        mixin_key,
        page_numbers,
        page_size,
        workers,
    )
    rows = fetch_search_rows(items, cookie, workers)
    fill_author_follower_counts(rows, cookie, workers)

    keyword_name = safe_filename(keyword) or "search"
    output_root = output_root or BASE_DIR / "output" / "search"
    output_dir = output_root / keyword_name
    output_dir.mkdir(parents=True, exist_ok=True)

    end_page = page + pages - 1
    run_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"search_{run_time}_{len(rows)}.csv"

    with open(output_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=SEARCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"搜索“{keyword}”第 {page}-{end_page} 页完成："
        f"保存 {len(rows)} 条，接口共 {total_results} 条；"
        f"已保存到 {output_path}"
    )
    return output_path


def crawl_search(
    keyword,
    page=1,
    pages=1,
    page_size=20,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """搜索视频，补齐互动数据并保存为 CSV。"""
    cookie = get_cookie_header()
    mixin_key = get_wbi_mixin_key(cookie)
    return _crawl_search_with_context(
        keyword,
        cookie,
        mixin_key,
        page=page,
        pages=pages,
        page_size=page_size,
        workers=workers,
    )


def crawl_hot_search(
    limit=10,
    page=1,
    pages=1,
    page_size=20,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """取得热搜词，并逐个执行关键词视频搜索。"""
    cookie = get_cookie_header()
    mixin_key = get_wbi_mixin_key(cookie)
    hot_items = request_with_retry(get_hot_search, cookie, limit)

    if not isinstance(hot_items, list):
        hot_items = []

    run_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        BASE_DIR / "output" / "search" / "hot-search" / run_time
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "hot_list.csv"
    summary_rows = []

    print(f"获取到 {len(hot_items)} 个热搜词")

    for rank, item in enumerate(hot_items, start=1):
        keyword = (
            item.get("keyword")
            or item.get("show_name")
            or ""
        ).strip()

        if not keyword:
            continue

        print(f"开始搜索热搜第 {rank} 名：{keyword}")
        result_file = ""
        status = "success"
        error = ""

        try:
            output_path = _crawl_search_with_context(
                keyword,
                cookie,
                mixin_key,
                output_root=output_dir,
                page=page,
                pages=pages,
                page_size=page_size,
                workers=workers,
            )
            result_file = str(output_path.relative_to(BASE_DIR))
        except (RuntimeError, ValueError) as exc:
            status = "failed"
            error = str(exc)
            print(f"热搜“{keyword}”搜索失败：{exc}")

        summary_rows.append(
            {
                "rank": rank,
                "keyword": keyword,
                "show_name": item.get("show_name") or keyword,
                "heat_score": item.get("heat_score", 0),
                "result_file": result_file,
                "status": status,
                "error": error,
            }
        )

    with open(summary_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "rank",
                "keyword",
                "show_name",
                "heat_score",
                "result_file",
                "status",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"热搜搜索完成，汇总文件：{summary_path}")
    return summary_path
