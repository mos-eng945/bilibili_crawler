"""
字幕和弹幕爬取入口。

整体思路：
1. 从命令行读取 BV 号，未提供时使用 DEFAULT_BVID。
2. 先确保 Bilibili 登录状态可用。
3. 保存视频信息。
4. 下载该视频的字幕。
5. 再打开视频并采集弹幕。
"""

import argparse

from login import ensure_login

# 所有爬虫默认使用的视频，只需要在这里修改
DEFAULT_BVID = "BV1V3Yn6wENr"


def main():
    from crawler_dm import goto
    from crawler_info import crawl_video_info
    from crawler_subtitle import crawl_subtitles

    parser = argparse.ArgumentParser(description="下载 Bilibili 字幕和弹幕")
    parser.add_argument(
        "bvid",
        nargs="?",
        default=DEFAULT_BVID,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    args = parser.parse_args()

    print("视频：", args.bvid)

    # 先确保登录态可用，再依次下载字幕和弹幕
    ensure_login()
    crawl_video_info(args.bvid)
    crawl_subtitles(args.bvid)
    goto(args.bvid)


if __name__ == "__main__":
    main()
