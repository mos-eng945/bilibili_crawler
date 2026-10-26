"""Bilibili 热搜批量视频搜索。"""

from bilibili_api import (
    get_hot_search,
)
from config import HOT_OUTPUT_DIR
from crawler_common import (
    SEARCH_DEFAULT_PAGE_SIZE,
    SEARCH_DEFAULT_WORKERS,
    SEARCH_MAX_WORKERS,
    request_with_retry,
    run_timestamp,
    write_csv,
)
from crawler_for import DETAIL_DEFAULT_WORKERS, crawl_bvids
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
        with_details=False,
        detail_workers=DETAIL_DEFAULT_WORKERS,
    ):
        self.session = session
        self.limit = limit
        self.page = page
        self.pages = pages
        self.page_size = page_size
        self.workers = workers
        self.with_details = bool(with_details)
        self.detail_workers = min(
            max(1, int(detail_workers)),
            SEARCH_MAX_WORKERS,
        )

    def run(self):
        hot_items = request_with_retry(
            get_hot_search,
            self.session.cookie,
            self.limit,
        )

        output_dir = get_hot_run_dir(run_timestamp())
        output_dir.mkdir(parents=True, exist_ok=True)
        keywords_dir = output_dir / "关键词"
        summary_path = output_dir / "hot_list.csv"
        summary_rows = []
        detail_groups = {}
        seen_bvids = set()

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
                search_crawler = SearchCrawler(
                    self.session,
                    keyword,
                    output_root=keywords_dir,
                    page=self.page,
                    pages=self.pages,
                    page_size=self.page_size,
                    workers=self.workers,
                    timestamped_output=False,
                )
                search_crawler.run()
                new_bvids = []

                for bvid in search_crawler.bvids:
                    if bvid in seen_bvids:
                        continue

                    seen_bvids.add(bvid)
                    new_bvids.append(bvid)

                if new_bvids:
                    detail_groups.setdefault(
                        search_crawler.output_dir,
                        [],
                    ).extend(new_bvids)
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

        if self.with_details:
            for keyword_dir, bvids in detail_groups.items():
                crawl_bvids(
                    bvids,
                    self.session,
                    output_root=keyword_dir / "视频详情",
                    workers=self.detail_workers,
                )

        return summary_path
