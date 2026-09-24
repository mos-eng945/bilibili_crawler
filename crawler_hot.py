"""Bilibili 热搜批量视频搜索。"""

from bilibili_api import (
    BASE_DIR,
    get_cookie_header,
    get_hot_search,
    get_wbi_mixin_key,
)
from crawler_common import (
    SEARCH_DEFAULT_WORKERS,
    request_with_retry,
    run_timestamp,
    write_csv,
)
from crawler_search import crawl_search_with_context


HOT_LIST_COLUMNS = [
    "rank",
    "keyword",
    "show_name",
    "heat_score",
    "result_file",
    "status",
    "error",
]


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

    run_time = run_timestamp()
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
            output_path = crawl_search_with_context(
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

    write_csv(summary_path, HOT_LIST_COLUMNS, summary_rows)

    print(f"热搜搜索完成，汇总文件：{summary_path}")
    return summary_path
