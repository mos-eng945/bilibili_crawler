"""Bilibili 数据采集命令行入口。"""

import argparse

from login import ensure_login

DEFAULT_BVID = "BV1UT42167xb"

OPTION_FLAGS = {
    "page": "-p",
    "page_size": "--page-size",
    "workers": "-w",
    "limit": "--limit",
    "language": "--language",
}


def parse_page_range(value):
    """把 START 或 START,END 转换成包含首尾的整数范围。"""
    parts = value.split(",")

    if len(parts) > 2:
        raise argparse.ArgumentTypeError("范围格式应为 START,END")

    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) == 2 else start
    except ValueError as exc:
        raise argparse.ArgumentTypeError("页码范围必须是整数") from exc

    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("页码必须满足 1 <= START <= END")

    return start, end


def build_parser():
    """创建 bilibili 命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="bilibili",
        description="下载 Bilibili 视频信息、评论、字幕、弹幕和搜索结果",
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "-l",
        "--login",
        action="store_true",
        help="确认登录状态，失效时重新登录",
    )
    actions.add_argument(
        "-i",
        "--info",
        action="store_true",
        help="采集视频信息",
    )
    actions.add_argument(
        "-c",
        "--comments",
        action="store_true",
        help="采集一级评论",
    )
    actions.add_argument(
        "-s",
        "--subtitles",
        action="store_true",
        help="采集字幕",
    )
    actions.add_argument(
        "-d",
        "--danmaku",
        action="store_true",
        help="采集弹幕",
    )
    actions.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="依次采集信息、评论、字幕和弹幕",
    )
    actions.add_argument(
        "-k",
        "--keyword",
        dest="keyword",
        metavar="关键词",
        help="按关键词搜索视频",
    )
    actions.add_argument(
        "-H",
        "--hot-search",
        action="store_true",
        help="对热搜词逐个执行视频搜索",
    )
    parser.add_argument(
        "bvid",
        nargs="?",
        default=None,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    parser.add_argument(
        "-p",
        dest="page",
        type=parse_page_range,
        metavar="START,END",
        default=None,
        help="字幕、弹幕或关键词搜索页范围，不适用于热搜",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=None,
        help="搜索结果每页数量，默认 20，最大 50",
    )
    parser.add_argument(
        "-w",
        dest="workers",
        type=int,
        default=None,
        help="搜索并发线程数，默认 3，最大 5",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="参与搜索的热搜数量，默认 10，最大 50",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="字幕语言，例如 zh-CN 或 ai-zh",
    )
    return parser


def reject_unused_options(parser, args, allowed):
    """拒绝当前操作不支持的参数，避免参数被静默忽略。"""
    if args.bvid is not None and "bvid" not in allowed:
        parser.error("BVID 不能与当前操作一起使用")

    for name, flag in OPTION_FLAGS.items():
        value = getattr(args, name)

        if value is not None and name not in allowed:
            parser.error(f"{flag} 不能与当前操作一起使用")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.login:
        reject_unused_options(parser, args, set())
        ensure_login()
        return

    bvid = args.bvid or DEFAULT_BVID

    if args.keyword is not None:
        reject_unused_options(
            parser,
            args,
            {"page", "page_size", "workers"},
        )

        if not args.keyword.strip():
            parser.error("搜索关键词不能为空")

        from crawler_search import crawl_search

        page_start, page_end = args.page or (1, 1)
        ensure_login()
        crawl_search(
            args.keyword,
            page=page_start,
            pages=page_end - page_start + 1,
            page_size=args.page_size or 20,
            workers=args.workers or 3,
        )
        return

    if args.hot_search:
        reject_unused_options(
            parser,
            args,
            {"page_size", "workers", "limit"},
        )

        from crawler_search import crawl_hot_search

        ensure_login()
        crawl_hot_search(
            limit=args.limit or 10,
            page=1,
            pages=1,
            page_size=args.page_size or 20,
            workers=args.workers or 3,
        )
        return

    if args.subtitles:
        reject_unused_options(parser, args, {"bvid", "page", "language"})
    elif args.danmaku:
        reject_unused_options(parser, args, {"bvid", "page"})
    else:
        reject_unused_options(parser, args, {"bvid"})

    from crawler_comment import crawl_comments
    from crawler_dm import goto
    from crawler_info import crawl_video_info
    from crawler_subtitle import crawl_subtitles

    print("视频：", bvid)
    ensure_login()

    if args.info:
        crawl_video_info(bvid)
    elif args.comments:
        crawl_comments(bvid)
    elif args.subtitles:
        crawl_subtitles(
            bvid,
            page_range=args.page,
            language=args.language,
        )
    elif args.danmaku:
        goto(bvid, page_range=args.page)
    elif args.all:
        crawl_video_info(bvid)
        crawl_comments(bvid)
        crawl_subtitles(bvid)
        goto(bvid)


if __name__ == "__main__":
    main()
