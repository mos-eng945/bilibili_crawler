"""读取爬虫 CSV 资源中的 BVID。"""

import csv
from pathlib import Path

from config import OUTPUT_DIR


SOURCE_NAMES = ("hot", "up", "search")
SOURCE_DIRECTORIES = {
    "hot": "热搜",
    "up": "UP主",
    "search": "关键词搜索",
}
DETAIL_DEFAULT_WORKERS = 2


def read_csv_bvids(path):
    """读取一个 CSV 文件中的 BVID，返回列表。"""
    bvids = []

    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or "bvid" not in reader.fieldnames:
            return bvids

        for row in reader:
            bvid = str(row.get("bvid") or "").strip()

            if len(bvid) >= 3 and bvid[:2].upper() == "BV":
                bvids.append(bvid)

    return bvids


def get_all_bvids(output_root=None):
    """遍历热搜、UP 主和搜索 CSV，返回去重后的 BVID 列表。"""
    root = Path(output_root) if output_root else OUTPUT_DIR
    bvids = []
    seen = set()

    for source in SOURCE_NAMES:
        source_root = root / SOURCE_DIRECTORIES[source]

        if not source_root.is_dir():
            continue

        for path in sorted(source_root.rglob("*.csv")):
            for bvid in read_csv_bvids(path):
                if bvid in seen:
                    continue

                seen.add(bvid)
                bvids.append(bvid)

    return bvids


def crawl_bvids(
    bvids,
    session,
    output_root=None,
    workers=None,
    page_range=None,
    language=None,
):
    """并发采集多个 BVID 的信息、字幕、弹幕和一级评论。"""
    from crawler_comment import CommentCrawler
    from crawler_common import (
        SEARCH_MAX_WORKERS,
        clear_log_prefix,
        log,
        run_concurrently,
        set_log_prefix,
    )
    from crawler_dm import DanmakuCrawler
    from crawler_info import VideoInfoCrawler
    from crawler_subtitle import SubtitleCrawler
    from session import VideoSession

    ordered_bvids = list(
        dict.fromkeys(
            str(bvid).strip()
            for bvid in bvids
            if str(bvid).strip()
        )
    )

    if not ordered_bvids:
        return []

    state = getattr(session, "_state", None)

    if workers is None:
        workers = DETAIL_DEFAULT_WORKERS

    worker_count = min(
        max(1, int(workers)),
        SEARCH_MAX_WORKERS,
    )
    labels = {
        bvid: f"{index:02d}/{len(ordered_bvids)} {bvid}"
        for index, bvid in enumerate(ordered_bvids, start=1)
    }

    def report_progress(completed, total):
        log(f"精爬进度：{completed}/{total}")
        log(f"::PROGRESS::{completed}/{total}")

    def crawl_one(bvid):
        set_log_prefix(labels[bvid])
        log("精爬开始")

        try:
            video_session = VideoSession(
                bvid,
                state,
                output_root=output_root,
            )
            VideoInfoCrawler(video_session).run()
            SubtitleCrawler(
                video_session,
                page_range=page_range,
                language=language,
            ).run()
            DanmakuCrawler(
                video_session,
                page_range=page_range,
            ).run()
            CommentCrawler(video_session).run()
        except Exception as exc:
            log(f"精爬失败：{exc}")
            return bvid, str(exc)
        else:
            log("精爬完成")
            return None
        finally:
            clear_log_prefix()

    log(f"::PROGRESS_START::{len(ordered_bvids)}")
    results = run_concurrently(
        crawl_one,
        ordered_bvids,
        worker_count,
        "精爬",
        on_progress=report_progress,
    )
    failures = [result for result in results if result is not None]
    print(
        f"精爬汇总：成功 {len(ordered_bvids) - len(failures)} 个，"
        f"失败 {len(failures)} 个，并发 {worker_count}"
    )
    log(
        f"::PROGRESS_DONE::{len(ordered_bvids) - len(failures)}/"
        f"{len(ordered_bvids)}",
    )
    return failures
