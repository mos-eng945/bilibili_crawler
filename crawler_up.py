"""Bilibili UP 主全部公开视频采集。"""

import math

from bilibili_api import (
    BASE_DIR,
    get_cookie_header,
    get_user_videos,
    get_wbi_mixin_key,
)
from crawler_common import (
    SEARCH_COLUMNS,
    SEARCH_DEFAULT_WORKERS,
    SEARCH_MAX_WORKERS,
    build_video_row,
    fetch_follower_count_safely,
    fetch_video_info_safely,
    format_published_at,
    request_with_retry,
    run_concurrently,
    timestamped_path,
    write_csv,
)


USER_VIDEO_DEFAULT_PAGE_SIZE = 30
USER_VIDEO_MAX_PAGE_SIZE = 50


def parse_user_video(
    item,
    video_info=None,
    author_follower_count=0,
):
    """把 UP 主空间中的视频条目转换成 CSV 行。"""
    author = item.get("author")
    mid = item.get("mid")
    like = item.get("like") or 0
    comment_count = item.get("review") or 0
    favorite_count = item.get("favorites") or 0
    share_count = item.get("share") or 0
    play_count = item.get("play") or 0
    danmaku_count = item.get("video_review") or 0
    published_at = format_published_at(
        item.get("created") or item.get("pubdate")
    )

    if video_info:
        owner = video_info.get("owner") or {}
        stat = video_info.get("stat") or {}
        author = owner.get("name") or author
        mid = owner.get("mid") or mid
        like = stat.get("like") or like
        comment_count = stat.get("reply") or comment_count
        favorite_count = stat.get("favorite") or favorite_count
        share_count = stat.get("share") or share_count
        play_count = stat.get("view") or play_count
        danmaku_count = stat.get("danmaku") or danmaku_count
        published_at = format_published_at(
            video_info.get("pubdate") or item.get("created")
        )

    return build_video_row(
        bvid=item.get("bvid"),
        title=item.get("title"),
        published_at=published_at,
        author=author,
        mid=mid,
        like=like,
        comment_count=comment_count,
        favorite_count=favorite_count,
        share_count=share_count,
        author_follower_count=author_follower_count,
        play_count=play_count,
        danmaku_count=danmaku_count,
    )


def fetch_user_video_items(
    mid,
    cookie,
    mixin_key,
    page_size=USER_VIDEO_DEFAULT_PAGE_SIZE,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """取得 UP 主公开视频的全部分页并按 BV 号去重。"""
    first_page = request_with_retry(
        get_user_videos,
        mid,
        cookie,
        mixin_key,
        page=1,
        page_size=page_size,
    )

    if not isinstance(first_page, dict):
        raise RuntimeError("UP 主视频接口返回格式异常")

    if first_page.get("is_risk"):
        raise RuntimeError("Bilibili 返回风控提示，请稍后重试")

    page_info = first_page.get("page")

    if not isinstance(page_info, dict):
        page_info = {}

    total_results = int(page_info.get("count") or 0)
    total_pages = max(1, math.ceil(total_results / page_size))
    page_numbers = list(range(2, total_pages + 1))

    def fetch_page(current_page):
        return request_with_retry(
            get_user_videos,
            mid,
            cookie,
            mixin_key,
            page=current_page,
            page_size=page_size,
        )

    page_results = [first_page]
    page_results.extend(
        run_concurrently(
            fetch_page,
            page_numbers,
            workers,
            "UP 主视频页",
        )
    )

    items = []
    seen_bvids = set()

    for data in page_results:
        if not isinstance(data, dict):
            continue

        if data.get("is_risk"):
            raise RuntimeError("Bilibili 返回风控提示，请稍后重试")

        list_data = data.get("list")

        if not isinstance(list_data, dict):
            continue

        for item in list_data.get("vlist") or []:
            bvid = item.get("bvid", "")

            if not bvid or bvid in seen_bvids:
                continue

            seen_bvids.add(bvid)
            items.append(item)

    return items, total_results


def _crawl_user_videos_with_context(
    mid,
    cookie,
    mixin_key,
    output_root=None,
    page_size=USER_VIDEO_DEFAULT_PAGE_SIZE,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """采集 UP 主全部公开视频并保存为 CSV。"""
    try:
        mid = int(mid)
    except (TypeError, ValueError) as exc:
        raise ValueError("UP 主 MID 必须是数字") from exc

    if mid <= 0:
        raise ValueError("UP 主 MID 必须大于 0")

    page_size = min(
        max(1, int(page_size)),
        USER_VIDEO_MAX_PAGE_SIZE,
    )
    workers = min(
        max(1, int(workers)),
        SEARCH_MAX_WORKERS,
    )

    items, total_results = fetch_user_video_items(
        mid,
        cookie,
        mixin_key,
        page_size=page_size,
        workers=workers,
    )
    follower_count = fetch_follower_count_safely(
        mid,
        "",
        cookie,
    )
    bvids = [item.get("bvid", "") for item in items]
    video_infos = run_concurrently(
        lambda bvid: fetch_video_info_safely(bvid, cookie),
        bvids,
        workers,
        "视频详情",
    )
    rows = [
        parse_user_video(
            item,
            video_info,
            follower_count,
        )
        for item, video_info in zip(items, video_infos)
    ]

    output_root = output_root or BASE_DIR / "output" / "search" / "up"
    output_dir = output_root / str(mid)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = timestamped_path(output_dir, "videos", len(rows))
    write_csv(output_path, SEARCH_COLUMNS, rows)

    print(
        f"UP 主 {mid} 视频采集完成："
        f"保存 {len(rows)} 条，接口共 {total_results} 条；"
        f"已保存到 {output_path}"
    )
    return output_path


def crawl_user_videos(
    mid,
    page_size=USER_VIDEO_DEFAULT_PAGE_SIZE,
    workers=SEARCH_DEFAULT_WORKERS,
):
    """采集 UP 主全部公开视频并保存为 CSV。"""
    cookie = get_cookie_header()
    mixin_key = get_wbi_mixin_key(cookie)
    return _crawl_user_videos_with_context(
        mid,
        cookie,
        mixin_key,
        page_size=page_size,
        workers=workers,
    )
