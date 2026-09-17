"""
Bilibili 数据爬取入口。

整体思路：
1. 从命令行读取 BV 号，未提供时使用 DEFAULT_BVID。
2. 先确保 Bilibili 登录状态可用。
3. 保存视频信息。
4. 下载全部一级评论。
5. 下载该视频的字幕。
6. 再打开视频并采集弹幕。
"""

import argparse

from login import ensure_login

# 所有爬虫默认使用的视频，只需要在这里修改
DEFAULT_BVID = "BV1UT42167xb"


def main():
    from crawler_dm import goto
    from crawler_comment import crawl_comments
    from crawler_info import crawl_video_info
    from crawler_subtitle import crawl_subtitles

    parser = argparse.ArgumentParser(description="下载 Bilibili 视频数据")
    parser.add_argument(
        "bvid",
        nargs="?",
        default=DEFAULT_BVID,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="只采集视频信息",
    )
    parser.add_argument(
        "--comments",
        action="store_true",
        help="只采集一级评论",
    )
    parser.add_argument(
        "--subtitles",
        action="store_true",
        help="只采集字幕",
    )
    parser.add_argument(
        "--danmaku",
        action="store_true",
        help="只采集弹幕",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="依次执行全部功能",
    )
    parser.add_argument(
        "--subtitle-page",
        type=int,
        default=None,
        help="只采集指定字幕分 P",
    )
    parser.add_argument(
        "--subtitle-language",
        default=None,
        help="只采集指定语言，例如 zh-CN 或 ai-zh",
    )
    parser.add_argument(
        "--danmaku-page",
        type=int,
        default=None,
        help="只采集指定弹幕分 P",
    )
    args = parser.parse_args()

    selected = {
        "info": args.info,
        "comments": args.comments,
        "subtitles": args.subtitles,
        "danmaku": args.danmaku,
    }

    if args.all:
        selected = {name: True for name in selected}

    if not any(selected.values()):
        parser.error("请至少选择一个功能：--info、--comments、--subtitles、--danmaku 或 --all")

    print("视频：", args.bvid)

    ensure_login()

    if selected["info"]:
        crawl_video_info(args.bvid)

    if selected["comments"]:
        crawl_comments(args.bvid)

    if selected["subtitles"]:
        crawl_subtitles(
            args.bvid,
            page_number=args.subtitle_page,
            language=args.subtitle_language,
        )

    if selected["danmaku"]:
        goto(args.bvid, page_number=args.danmaku_page)


if __name__ == "__main__":
    main()
