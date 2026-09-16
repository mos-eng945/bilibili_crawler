"""
Bilibili 弹幕爬虫。

整体思路：
1. 加载登录状态并打开视频页面。
2. 监听浏览器发出的 seg.so 弹幕接口响应。
3. 使用 Protobuf 解码响应，去重后写入视频目录下的 CSV。
4. 分段跳转视频播放位置，触发不同时间范围的弹幕请求。
"""

import csv
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

import dm_pb2
from bilibili_api import get_cookie_header, get_video_info
from login import STATE_FILE, ensure_login
from main import DEFAULT_BVID
from video_paths import get_video_dir

# 弹幕接口通常一次覆盖约 120 秒
SEEK_STEP_SECONDS = 120
SEEK_WAIT_MS = 2500


def crawl_page(page, bvid, page_info, total_pages, video_dir, use_page_suffix):
    """采集一个分 P 的弹幕并写入独立 CSV。"""
    page_number = page_info.get("page", 1)
    expected_oid = page_info.get("cid")
    part = page_info.get("part", "")

    if not expected_oid:
        print(f"跳过 P{page_number}：没有 cid")
        return 0

    expected_oid = str(expected_oid)
    video_dir.mkdir(parents=True, exist_ok=True)

    if use_page_suffix:
        csv_file = video_dir / f"danmaku_{bvid}_p{page_number}.csv"
    else:
        csv_file = video_dir / f"danmaku_{bvid}.csv"

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as file:
        csv.writer(file).writerow(["时间(ms)", "内容", "颜色", "模式", "用户Hash"])

    seen_danmaku = set()
    saved_count = 0

    def handle_response(response):
        nonlocal saved_count

        parsed_url = urlparse(response.url)

        if not parsed_url.path.lower().endswith("/seg.so") or not response.ok:
            return

        oid = parse_qs(parsed_url.query).get("oid", [None])[0]

        if oid != expected_oid:
            return

        reply = dm_pb2.DmSegMobileReply()
        reply.ParseFromString(response.body())

        rows = []

        for elem in reply.elems:
            key = (elem.id, elem.progress, elem.content)

            if key in seen_danmaku:
                continue

            seen_danmaku.add(key)
            rows.append(
                [
                    elem.progress,
                    elem.content,
                    elem.color,
                    elem.mode,
                    elem.midHash,
                ]
            )

        if not rows:
            return

        with open(csv_file, "a", newline="", encoding="utf-8-sig") as file:
            csv.writer(file).writerows(rows)

        saved_count += len(rows)
        print(
            f"P{page_number} 新增 {len(rows)} 条，"
            f"累计 {saved_count} 条"
        )

    page.on("response", handle_response)

    try:
        print(f"开始采集 P{page_number}/{total_pages}：{part}")

        page.goto(
            f"https://www.bilibili.com/video/{bvid}?p={page_number}",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        page.wait_for_timeout(5000)

        videos = page.locator("video")

        if videos.count() == 0:
            print(f"P{page_number} 没有找到视频播放器")
            return saved_count

        video = videos.first
        page.wait_for_function("document.querySelector('video')?.readyState >= 1")
        duration = float(video.evaluate("video => video.duration"))
        print(f"P{page_number} 视频长度：{duration:.1f} 秒")

        current_time = 0

        while current_time < duration:
            print(f"P{page_number} 跳到：{current_time:.0f} 秒")

            video.evaluate(
                """
                (video, time) => {
                    video.pause();
                    video.currentTime = Math.min(
                        time,
                        Math.max(0, video.duration - 1)
                    );
                    video.muted = true;
                    return video.play();
                }
                """,
                current_time,
            )

            page.wait_for_timeout(SEEK_WAIT_MS)
            current_time += SEEK_STEP_SECONDS

        print(f"P{page_number} 完成，共写入 {saved_count} 条弹幕")
        return saved_count
    finally:
        page.remove_listener("response", handle_response)


def goto(bvid, page_number=None):
    """采集视频全部或指定分 P 的弹幕。"""
    cookie = get_cookie_header()
    video_info = get_video_info(bvid, cookie)
    pages = video_info.get("pages", [])
    video_dir = get_video_dir(video_info)

    if not pages:
        raise RuntimeError(f"没有找到视频分 P：{bvid}")

    video_page_count = len(pages)

    if page_number is not None:
        pages = [item for item in pages if item.get("page") == page_number]

        if not pages:
            raise RuntimeError(f"视频 {bvid} 没有第 {page_number} 个分 P")

    # =========================
    # 1. 启动浏览器
    # =========================

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")

        context = browser.new_context(storage_state=STATE_FILE)

        page = context.new_page()

        total_saved = 0

        for page_info in pages:
            total_saved += crawl_page(
                page,
                bvid,
                page_info,
                video_page_count,
                video_dir,
                video_page_count > 1,
            )

        print(f"爬取完成，共写入 {total_saved} 条弹幕")

        browser.close()


# 单独运行本文件也能用：python crawler.py
if __name__ == "__main__":
    ensure_login()
    goto(DEFAULT_BVID)
