"""
Bilibili 弹幕爬虫（直连接口）。

整体思路：
1. 从视频信息取每个分 P 的 cid、aid 和时长。
2. 按 360 秒一段请求播放器使用的弹幕分段接口。
3. 使用 Protobuf 解码响应，去重后写入视频目录下的 CSV。
"""

import csv
import math
import time
from pathlib import Path

import dm_pb2
from bilibili_api import DANMAKU_SEGMENT_SECONDS, fetch_danmaku_segment
from config import DEFAULT_BVID
from crawler_common import (
    format_china_time,
    format_milliseconds,
    request_with_retry,
    safe_filename,
)
from login import ensure_login
from session import VideoSession

# 连续请求分段之间的停顿，降低触发风控的概率
REQUEST_INTERVAL_SECONDS = 0.5
# 连续这么多段都失败时中止，避免在登录失效等情况下空转
MAX_CONSECUTIVE_FAILURES = 3


def get_danmaku_paths(video_dir, pages):
    """为每个分 P 生成弹幕 CSV 路径，标题重复时追加 P 号。"""
    paths = {}
    used_names = set()

    for page_info in pages:
        page_number = page_info.get("page", 1)
        part = str(page_info.get("part") or "").strip()
        stem = Path(part).stem if part else ""
        base = (
            f"danmaku_{safe_filename(stem)}"
            if stem
            else f"danmaku_p{page_number}"
        )
        name = f"{base}.csv"

        if name in used_names:
            name = f"{base}_p{page_number}.csv"

        used_names.add(name)
        paths[page_number] = Path(video_dir) / name

    return paths


def segment_count(duration):
    """按每段 360 秒计算需要请求的弹幕分段数。"""
    return math.ceil(float(duration) / DANMAKU_SEGMENT_SECONDS)


def parse_danmaku_rows(raw, seen):
    """解码一个分段响应，返回去重后的 CSV 行。"""
    reply = dm_pb2.DmSegMobileReply()  # pyright: ignore[reportAttributeAccessIssue]
    reply.ParseFromString(raw)
    rows = []

    for elem in reply.elems:
        key = (elem.id, elem.progress, elem.content)

        if key in seen:
            continue

        seen.add(key)
        rows.append(
            [
                elem.id,
                format_milliseconds(elem.progress),
                elem.weight,
                elem.content,
                elem.midHash,
                format_china_time(elem.ctime),
                elem.pool,
            ]
        )

    return rows


def crawl_page(session, page_info, total_pages, csv_file):
    """
    采集一个分 P 的弹幕并写入独立 CSV。

    参数：
        session: VideoSession，提供 cookie、WBI 密钥和视频信息。
        page_info: 当前分 P 的元信息字典，包含 page（第几 P）、
        cid（弹幕 oid）、part（分 P 标题）和 duration（秒）。
        total_pages: 分 P 总数，仅用于打印采集进度。
        csv_file: 当前分 P 的弹幕 CSV 输出路径。

    返回：
        本次实际写入的弹幕条数；缺少 cid 时返回 0。
    """
    page_number = page_info.get("page", 1)
    cid = page_info.get("cid")
    part = page_info.get("part", "")
    aid = session.video_info.get("aid")
    duration = page_info.get("duration") or session.video_info.get("duration", 0)

    if not cid:
        print(f"跳过 P{page_number}：没有 cid")
        return 0

    if not aid:
        raise RuntimeError(f"视频信息缺少 aid，无法采集弹幕：{session.bvid}")

    if not duration or float(duration) <= 0:
        raise RuntimeError(f"P{page_number} 缺少有效时长，无法计算弹幕分段")

    total_segments = segment_count(duration)
    seen_danmaku = set()
    saved_count = 0
    failures = 0

    csv_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"开始采集 P{page_number}/{total_pages}：{part}（{total_segments} 段）")

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "弹幕id",
                "出现时间",
                "权重",
                "内容",
                "哈希",
                "发送时间",
                "弹幕池",
            ]
        )

        for segment_index in range(1, total_segments + 1):
            try:
                raw = request_with_retry(
                    fetch_danmaku_segment,
                    cid,
                    aid,
                    segment_index,
                    session.cookie,
                    session.mixin_key,
                )
            except RuntimeError as exc:
                failures += 1
                print(f"P{page_number} 第 {segment_index} 段请求失败：{exc}")

                if failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(
                        f"P{page_number} 连续 {failures} 段请求失败，中止采集"
                    ) from exc

                time.sleep(REQUEST_INTERVAL_SECONDS)
                continue

            failures = 0
            rows = parse_danmaku_rows(raw, seen_danmaku) if raw else []

            if rows:
                writer.writerows(rows)
                saved_count += len(rows)

            print(
                f"P{page_number} 第 {segment_index}/{total_segments} 段"
                f"新增 {len(rows)} 条，累计 {saved_count} 条"
            )

            if segment_index < total_segments:
                time.sleep(REQUEST_INTERVAL_SECONDS)

    print(f"P{page_number} 完成，共写入 {saved_count} 条弹幕")
    return saved_count


class DanmakuCrawler:
    """直连弹幕分段接口，采集全部或指定分 P 的弹幕。"""

    def __init__(self, session, page_range=None):
        self.session = session  # VideoSession 实例
        self.page_range = page_range

    def run(self):
        # 从会话里取出要采集的分 P 列表和每个分 P 的输出路径
        pages = self.session.pages(self.page_range)
        video_page_count = self.session.page_count
        csv_paths = get_danmaku_paths(self.session.video_dir, pages)
        total_saved = 0

        for page_info in pages:
            total_saved += crawl_page(
                self.session,
                page_info,
                video_page_count,
                csv_paths[page_info.get("page", 1)],
            )

        print(f"爬取完成，共写入 {total_saved} 条弹幕")
        return total_saved


# 统一命令行入口：bilibili -d
if __name__ == "__main__":
    ensure_login()
    DanmakuCrawler(VideoSession("BV1Uw826pE7J")).run()
