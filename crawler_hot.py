"""Bilibili 热搜批量视频搜索。"""

from bilibili_api import (
    get_hot_search,
)
from config import HOT_OUTPUT_DIR
from crawler_common import (
    SEARCH_DEFAULT_PAGE_SIZE,
    SEARCH_DEFAULT_WORKERS,
    request_with_retry,
    run_timestamp,
    write_csv,
)
from crawler_search import SearchCrawler


def get_hot_run_dir(run_time):
    """生成某次热搜运行的目录：`hot/{运行时间}/`。"""
    return HOT_OUTPUT_DIR / run_time


HOT_LIST_COLUMNS = [
    "rank",
    "keyword",
    "show_name",
    "heat_score",
    "status",
    "error",
]


class HotSearchCrawler:
    """取得热搜词，逐个搜索视频并汇总结果。"""

    def __init__(
        self,
        session,
        limit=10,
        page=1,
        pages=1,
        page_size=SEARCH_DEFAULT_PAGE_SIZE,
        workers=SEARCH_DEFAULT_WORKERS,
    ):
        self.session = session
        self.limit = limit
        self.page = page
        self.pages = pages
        self.page_size = page_size
        self.workers = workers

    def run(self):
        hot_items = request_with_retry(
            get_hot_search,
            self.session.cookie,
            self.limit,
        )

        output_dir = get_hot_run_dir(run_timestamp())
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
            status = "success"
            error = ""

            try:
                SearchCrawler(
                    self.session,
                    keyword,
                    output_root=output_dir,
                    page=self.page,
                    pages=self.pages,
                    page_size=self.page_size,
                    workers=self.workers,
                ).run()
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
                    "status": status,
                    "error": error,
                }
            )

        write_csv(summary_path, HOT_LIST_COLUMNS, summary_rows)

        print(f"热搜搜索完成，汇总文件：{summary_path}")
        return summary_path
