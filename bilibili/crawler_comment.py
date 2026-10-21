"""Bilibili 一级评论下载器。"""

import argparse
import re
from datetime import datetime

from bilibili_api import fetch_comment_page
from config import DEFAULT_BVID
from crawler_common import normalize_url, request_with_retry, write_csv
from login import ensure_login
from session import VideoSession

COMMENT_COLUMNS = [
    "rpid",
    "mid",
    "user_name",
    "user_level",
    "sex",
    "vip",
    "message",
    "ctime_text",
    "like",
    "reply_count",
    "state",
    "ip_location",
    "image_urls",
]
COMMENT_MODE_TIME = 2
COMMENT_PAGE_SIZE = 30
COMMENT_PROGRESS_PAGE_INTERVAL = 10


def parse_image_urls(content):
    """提取评论图片地址，不下载图片。"""
    urls = []

    for item in content.get("pictures") or []:
        url = normalize_url(item.get("img_src"))

        if url:
            urls.append(url)

    return urls


def normalize_text(value):
    """把评论文本规范成适合 CSV 的单行内容。"""
    text = str(value or "")
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n+", r"\\n", text)
    return text.strip()


def parse_comment(comment):
    """把评论接口数据转换成轻量记录。"""
    member = comment.get("member") or {}
    level_info = member.get("level_info") or {}
    vip = member.get("vip") or {}
    content = comment.get("content") or {}
    reply_control = comment.get("reply_control") or {}
    ip_location = normalize_text(reply_control.get("location", ""))
    ctime = comment.get("ctime", 0)

    for prefix in ("IP属地：", "IP属地:"):
        if ip_location.startswith(prefix):
            ip_location = ip_location[len(prefix) :].strip()
            break

    try:
        ctime_text = datetime.fromtimestamp(int(ctime)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError, OSError):
        ctime_text = ""

    return {
        "rpid": comment.get("rpid"),
        "mid": comment.get("mid"),
        "user_name": normalize_text(member.get("uname", "")),
        "user_level": level_info.get("current_level", 0),
        "sex": normalize_text(member.get("sex", "")),
        "vip": vip.get("vipStatus", 0),
        "message": normalize_text(content.get("message", "")),
        "ctime_text": ctime_text,
        "like": comment.get("like", 0),
        "reply_count": comment.get("count", 0),
        "state": comment.get("state", 0),
        "ip_location": ip_location,
        "image_urls": parse_image_urls(content),
    }


def extract_page_comments(data, include_top=False):
    """提取当前页的一级评论并转换成轻量记录。"""
    replies = []

    if include_top:
        replies.extend(data.get("top_replies") or [])

    replies.extend(data.get("replies") or [])
    return [parse_comment(comment) for comment in replies]


def merge_comment_rows(rows):
    """按 rpid 去重，并按发布时间从新到旧排列。"""
    merged = []
    seen = set()

    for row in rows:
        rpid = str(row.get("rpid") or "")

        if not rpid or rpid in seen:
            continue

        seen.add(rpid)
        merged.append(row)

    merged.sort(
        key=lambda row: str(row.get("ctime_text") or ""),
        reverse=True,
    )
    return merged


class CommentCrawler:
    """按 WBI 游标分页、时间顺序采集视频的全部一级评论。"""

    def __init__(self, session):
        self.session = session

    def run(self):
        oid = self.session.video_info.get("aid")

        if not oid:
            raise RuntimeError(f"视频 {self.session.bvid} 没有返回 aid")

        video_dir = self.session.video_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / f"comments_{self.session.bvid}.csv"
        cursor = {}
        page_number = 0
        total_reply_count = 0
        collected_rows = []
        seen_rpids = set()

        print(f"开始完整采集评论：{output_path}")
        print(f"评论排序：时间顺序，每页 {COMMENT_PAGE_SIZE} 条")
        print("开始采集评论，使用 WBI 游标分页")

        while True:
            data = request_with_retry(
                fetch_comment_page,
                oid,
                cursor,
                self.session.cookie,
                self.session.mixin_key,
                COMMENT_MODE_TIME,
                COMMENT_PAGE_SIZE,
            )
            page_number += 1
            page_comments = extract_page_comments(
                data,
                include_top=page_number == 1,
            )
            new_rows = []

            for comment in page_comments:
                rpid = str(comment["rpid"] or "")

                if not rpid or rpid in seen_rpids:
                    continue

                seen_rpids.add(rpid)
                new_rows.append(
                    {
                        **comment,
                        "image_urls": "|".join(comment["image_urls"]),
                    }
                )

            collected_rows.extend(new_rows)

            cursor = data.get("cursor") or {}
            total_reply_count = cursor.get("all_count") or total_reply_count
            is_end = bool(cursor.get("is_end"))
            next_offset = (cursor.get("pagination_reply") or {}).get("next_offset")

            if (
                page_number == 1
                or page_number % COMMENT_PROGRESS_PAGE_INTERVAL == 0
                or is_end
            ):
                print(
                    f"已获取第 {page_number} 页，"
                    f"本页获取 {len(new_rows)} 条，"
                    f"累计 {len(seen_rpids)} 条；"
                    f"视频总评论 {total_reply_count} 条（含子评论）"
                )

            if is_end or not next_offset:
                break

        saved_rows = merge_comment_rows(collected_rows)
        write_csv(output_path, COMMENT_COLUMNS, saved_rows)
        saved_count = len(saved_rows)

        print(
            f"评论已保存：{output_path}，"
            f"共 {saved_count} 条一级评论；"
            f"视频总评论 {total_reply_count} 条（含子评论）"
        )
        return output_path


def main():
    parser = argparse.ArgumentParser(description="下载 Bilibili 一级评论")
    parser.add_argument(
        "bvid",
        nargs="?",
        default=DEFAULT_BVID,
        help="视频 BV 号，不填写时使用 DEFAULT_BVID",
    )
    args = parser.parse_args()

    state = ensure_login()
    CommentCrawler(VideoSession(args.bvid, state)).run()


if __name__ == "__main__":
    main()
