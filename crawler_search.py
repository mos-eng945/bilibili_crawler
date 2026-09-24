"""Bilibili 关键词视频搜索。"""

from bilibili_api import (
    BASE_DIR,
    get_cookie_header,
    get_wbi_mixin_key,
    safe_filename,
    search_videos,
)
from crawler_common import (
    SEARCH_COLUMNS,
    SEARCH_DEFAULT_WORKERS,
    SEARCH_MAX_WORKERS,
    build_video_row,
    clean_html_text,
    fetch_follower_count_safely,
    fetch_video_info_safely,
    format_published_at,
    request_with_retry,
    run_concurrently,
    timestamped_path,
    write_csv,
)


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

    return build_video_row(
        bvid=bvid,
        title=item.get("title"),
        published_at=published_at,
        author=author,
        mid=mid,
        like=like,
        comment_count=comment_count,
        favorite_count=favorite_count,
        share_count=share_count,
        author_follower_count=0,
        play_count=play_count,
        danmaku_count=danmaku_count,
    )


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


def crawl_search_with_context(
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
    output_path = timestamped_path(output_dir, "search", len(rows))
    write_csv(output_path, SEARCH_COLUMNS, rows)

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
    return crawl_search_with_context(
        keyword,
        cookie,
        mixin_key,
        page=page,
        pages=pages,
        page_size=page_size,
        workers=workers,
    )
