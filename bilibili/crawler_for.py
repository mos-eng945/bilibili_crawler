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
DETAIL_DEFAULT_WORKERS = 3


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
    """返回热搜、UP 主和搜索 CSV 中的 BVID。"""
    root = OUTPUT_DIR

    if output_root:
        root = Path(output_root)

    bvids = []

    for source_name in SOURCE_NAMES:
        source_dir = root / SOURCE_DIRECTORIES[source_name]

        if not source_dir.is_dir():
            continue

        for path in sorted(source_dir.rglob("*.csv")):
            bvids.extend(read_csv_bvids(path))

    return bvids


def _crawl_one_bvid(
    bvid,
    session_state,
    output_root,
    page_range,
    language,
):
    """采集单个 BVID，失败时返回错误信息。"""
    from crawler_comment import CommentCrawler
    from crawler_common import log
    from crawler_dm import DanmakuCrawler
    from crawler_info import VideoInfoCrawler
    from crawler_subtitle import SubtitleCrawler
    from session import VideoSession

    log(f"{bvid} 全部采集")

    try:
        video_session = VideoSession(
            bvid,
            session_state,
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
        log(f"{bvid} 精爬失败：{exc}")
        return bvid, str(exc)
    else:
        log(f"{bvid} 精爬完成")
        return None


def crawl_bvids(
    bvids,
    session,
    output_root=None,
    workers=None,
    page_range=None,
    language=None,
):
    """并发采集多个 BVID 的信息、字幕、弹幕和一级评论。"""
    from crawler_common import (
        SEARCH_MAX_WORKERS,
        clear_log_prefix,
        log,
        run_concurrently,
        set_log_prefix,
    )

    ordered_bvids = []
    seen_bvids = set()

    for bvid in bvids:
        normalized_bvid = str(bvid).strip()

        if not normalized_bvid:
            continue

        if normalized_bvid in seen_bvids:
            continue

        seen_bvids.add(normalized_bvid)
        ordered_bvids.append(normalized_bvid)

    if not ordered_bvids:
        return []

    session_state = getattr(session, "_state", None)

    if workers is None:
        workers = DETAIL_DEFAULT_WORKERS

    worker_count = int(workers)

    if worker_count < 1:
        worker_count = 1

    if worker_count > SEARCH_MAX_WORKERS:
        worker_count = SEARCH_MAX_WORKERS

    def report_progress(completed, total):
        log(f"爬取进度：{completed}/{total}")
        log(f"::PROGRESS::{completed}/{total}")

    tasks = []

    for index, bvid in enumerate(ordered_bvids, start=1):
        tasks.append((index, bvid))

    def crawl_one(task):
        index, bvid = task
        set_log_prefix(f"{index:02d}/{len(ordered_bvids)} {bvid}")

        try:
            return _crawl_one_bvid(
                bvid,
                session_state,
                output_root,
                page_range,
                language,
            )
        finally:
            clear_log_prefix()

    log(f"::PROGRESS_START::{len(ordered_bvids)}")
    results = run_concurrently(
        crawl_one,
        tasks,
        worker_count,
        "精爬",
        on_progress=report_progress,
        ordered_logs=True,
    )
    failures = []

    for result in results:
        if result is not None:
            failures.append(result)

    success_count = len(ordered_bvids) - len(failures)

    print(
        f"精爬汇总：成功 {success_count} 个，"
        f"失败 {len(failures)} 个，并发 {worker_count}"
    )
    log(
        f"::PROGRESS_DONE::{success_count}/{len(ordered_bvids)}",
    )
    return failures
