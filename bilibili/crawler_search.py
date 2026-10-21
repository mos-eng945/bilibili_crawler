"""Bilibili 关键词视频搜索。"""

from pathlib import Path

from bilibili_api import (
    search_videos,
)
from config import SEARCH_OUTPUT_DIR
from crawler_common import (
    SEARCH_COLUMNS,
    SEARCH_DEFAULT_PAGE_SIZE,
    SEARCH_DEFAULT_WORKERS,
    SEARCH_MAX_PAGE_SIZE,
    SEARCH_MAX_WORKERS,
    build_video_row,
    clean_html_text,
    fetch_follower_count_safely,
    format_published_at,
    normalize_url,
    parse_duration_seconds,
    request_with_retry,
    run_concurrently,
    safe_filename,
    timestamped_path,
    write_csv,
)

# 搜索接口不返回分享数，写文件时去掉这一列，避免整列 0 被当成真实数据
OUTPUT_COLUMNS = [column for column in SEARCH_COLUMNS if column != "share_count"]


def get_search_dir(keyword, root=None):
    """生成关键词搜索目录：`search/{关键词}/`。"""
    root = root or SEARCH_OUTPUT_DIR
    return Path(root) / (safe_filename(keyword) or "search")


def parse_search_video(item):
    """把搜索结果转换成 CSV 行。"""
    bvid = item.get("bvid", "")
    published_at = format_published_at(item.get("pubdate"))
    mid = item.get("mid")
    author = clean_html_text(item.get("author"))
    partition = item.get("typename") or item.get("tname") or ""
    tags = item.get("tag") or item.get("tags") or ""
    duration_seconds = parse_duration_seconds(
        item.get("duration") or item.get("length")
    )
    cover_url = normalize_url(item.get("pic") or item.get("cover"))
    like = item.get("like", 0)
    comment_count = item.get("review", 0)
    favorite_count = item.get("favorites", 0)
    share_count = 0  # 搜索接口没有分享数，该列不会写入（见 OUTPUT_COLUMNS）
    play_count = item.get("play", 0)
    danmaku_count = item.get("video_review", 0)

    return build_video_row(
        bvid=bvid,
        title=item.get("title"),
        published_at=published_at,
        author=author,
        mid=mid,
        partition=partition,
        tags=tags,
        duration_seconds=duration_seconds,
        cover_url=cover_url,
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


def build_search_rows(items):
    """把搜索结果转换成 CSV 行。"""
    return [parse_search_video(item) for item in items]


def fill_author_follower_counts(rows, cookie, workers):
    """按作者 mid 并发补充搜索结果的粉丝数。"""
    mids = list(dict.fromkeys(row["mid"] for row in rows if row["mid"]))
    author_names = {row["mid"]: row["author"] for row in rows if row["mid"]}
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


class SearchCrawler:
    """按关键词搜索视频，补齐互动数据并保存为 CSV。"""

    def __init__(
        self,
        session,
        keyword,
        output_root=None,
        page=1,
        pages=1,
        page_size=SEARCH_DEFAULT_PAGE_SIZE,
        workers=SEARCH_DEFAULT_WORKERS,
    ):
        self.session = session
        self.keyword = str(keyword).strip()
        self.output_root = output_root
        self.page = max(1, int(page))
        self.pages = max(1, int(pages))
        self.page_size = min(
            max(1, int(page_size)),
            SEARCH_MAX_PAGE_SIZE,
        )
        self.workers = min(
            max(1, int(workers)),
            SEARCH_MAX_WORKERS,
        )

        if not self.keyword:
            raise ValueError("搜索关键词不能为空")

    def run(self):
        page_numbers = list(range(self.page, self.page + self.pages))
        items, total_results = fetch_search_items(
            self.keyword,
            self.session.cookie,
            self.session.mixin_key,
            page_numbers,
            self.page_size,
            self.workers,
        )
        rows = build_search_rows(items)
        fill_author_follower_counts(
            rows,
            self.session.cookie,
            self.workers,
        )

        output_dir = get_search_dir(self.keyword, self.output_root)
        output_dir.mkdir(parents=True, exist_ok=True)

        end_page = self.page + self.pages - 1
        output_path = timestamped_path(output_dir, "search", len(rows))
        write_csv(output_path, OUTPUT_COLUMNS, rows)

        print(
            f"搜索“{self.keyword}”第 {self.page}-{end_page} 页完成："
            f"保存 {len(rows)} 条，接口共 {total_results} 条；"
            f"已保存到 {output_path}"
        )
        return output_path
