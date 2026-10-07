"""Bilibili 数据采集命令行入口。"""

import argparse

from config import (
    DEFAULT_BVID,
    parse_page_range,
    resolve_search_page_range,
)
from crawler_common import SEARCH_DEFAULT_WORKERS
from login import ensure_login

OPTION_FLAGS = {
    "page": "-p",
    "search_page": "--search-page",
    "page_size": "--page-size",
    "workers": "-w",
    "limit": "--limit",
    "language": "--language",
    "comment_mode": "--comment-mode",
    "comment_page_size": "--comment-page-size",
}


def parse_comment_page_size(value):
    """校验评论每页数量。"""
    try:
        page_size = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("评论每页数量必须是整数") from exc

    if not 1 <= page_size <= 30:
        raise argparse.ArgumentTypeError(
            "评论每页数量必须满足 1 <= PAGE_SIZE <= 30"
        )

    return page_size


def build_parser():
    """创建 bilibili 命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="bilibili",
        description=(
            "下载 Bilibili 视频信息、评论、字幕、弹幕、搜索结果"
            "和 UP 主全部视频"
        ),
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
        help="依次采集信息、字幕、弹幕和评论",
    )
    actions.add_argument(
        "-k",
        "--keyword",
        dest="keyword",
        metavar="关键词",
        help="按关键词搜索视频",
    )
    actions.add_argument(
        "-m",
        "--mid",
        dest="mid",
        metavar="MID",
        help="采集指定 UP 主的全部公开视频",
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
        help="字幕或弹幕分 P 范围",
    )
    parser.add_argument(
        "--search-page",
        dest="search_page",
        type=parse_page_range,
        metavar="START,END",
        default=None,
        help="关键词搜索页范围，单值 10 表示 1-10",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=None,
        help="搜索或 UP 主视频每页数量，最大 50",
    )
    parser.add_argument(
        "-w",
        dest="workers",
        type=int,
        default=None,
        help=(
            "关键词搜索或 UP 主视频并发线程数，"
            f"默认 {SEARCH_DEFAULT_WORKERS}，最大 10"
        ),
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
    parser.add_argument(
        "--comment-mode",
        choices=("time", "hot"),
        default=None,
        help="评论排序：time 按时间，hot 按热门",
    )
    parser.add_argument(
        "--comment-page-size",
        type=parse_comment_page_size,
        default=None,
        help="评论每页数量，默认 30，最大 30",
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

    if args.mid is not None:
        reject_unused_options(
            parser,
            args,
            {"page_size", "workers"},
        )

        if not args.mid.strip().isdigit() or int(args.mid) <= 0:
            parser.error("UP 主 MID 必须是大于 0 的数字")

        from crawler_up import UpVideosCrawler
        from session import Session

        ensure_login()
        UpVideosCrawler(
            Session(),
            args.mid,
            page_size=args.page_size or 30,
            workers=args.workers or SEARCH_DEFAULT_WORKERS,
        ).run()
        return

    if args.keyword is not None:
        reject_unused_options(
            parser,
            args,
            {"search_page", "page_size", "workers"},
        )

        if not args.keyword.strip():
            parser.error("搜索关键词不能为空")

        from crawler_search import SearchCrawler
        from session import Session

        page_start, page_end = resolve_search_page_range(args.search_page)
        ensure_login()
        SearchCrawler(
            Session(),
            args.keyword,
            page=page_start,
            pages=page_end - page_start + 1,
            page_size=args.page_size or 20,
            workers=args.workers or SEARCH_DEFAULT_WORKERS,
        ).run()
        return

    if args.hot_search:
        reject_unused_options(
            parser,
            args,
            {"page_size", "workers", "limit"},
        )

        from crawler_hot import HotSearchCrawler
        from session import Session

        ensure_login()
        HotSearchCrawler(
            Session(),
            limit=args.limit or 10,
            page=1,
            pages=1,
            page_size=args.page_size or 20,
            workers=args.workers or SEARCH_DEFAULT_WORKERS,
        ).run()
        return

    if args.subtitles:
        reject_unused_options(parser, args, {"bvid", "page", "language"})
    elif args.danmaku:
        reject_unused_options(parser, args, {"bvid", "page"})
    elif args.comments or args.all:
        reject_unused_options(
            parser,
            args,
            {"bvid", "comment_mode", "comment_page_size"},
        )
    else:
        reject_unused_options(parser, args, {"bvid"})

    from crawler_comment import CommentCrawler
    from crawler_dm import DanmakuCrawler
    from crawler_info import VideoInfoCrawler
    from crawler_subtitle import SubtitleCrawler
    from session import VideoSession

    print("视频：", bvid)
    ensure_login()

    session = VideoSession(bvid)
    comment_mode = 3 if args.comment_mode == "hot" else 2
    comment_page_size = args.comment_page_size or 30

    if args.info:
        VideoInfoCrawler(session).run()
    elif args.comments:
        CommentCrawler(
            session,
            mode=comment_mode,
            page_size=comment_page_size,
        ).run()
    elif args.subtitles:
        SubtitleCrawler(
            session,
            page_range=args.page,
            language=args.language,
        ).run()
    elif args.danmaku:
        DanmakuCrawler(session, page_range=args.page).run()
    elif args.all:
        VideoInfoCrawler(session).run()
        SubtitleCrawler(session).run()
        DanmakuCrawler(session).run()
        # 评论最慢，放到最后，先拿到其余结果
        CommentCrawler(
            session,
            mode=comment_mode,
            page_size=comment_page_size,
        ).run()


if __name__ == "__main__":
    main()
