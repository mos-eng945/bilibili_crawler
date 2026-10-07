"""Bilibili 一级评论下载器。"""

import argparse
import json
import re
import time

from bilibili_api import (
    request_wbi_json,
)
from config import DEFAULT_BVID
from crawler_common import normalize_url, write_csv
from login import ensure_login
from session import VideoSession

COMMENT_COLUMNS = [
    "rpid",
    "mid",
    "user_name",
    "user_level",
    "message",
    "ctime",
    "like",
    "reply_count",
    "state",
    "ip_location",
    "image_urls",
]
COMMENT_MODE_TIME = 2
COMMENT_MODE_HOT = 3
COMMENT_PAGE_SIZE = 30
COMMENT_MAX_PAGE_SIZE = 30
COMMENT_WEB_LOCATION = 1315875
COMMENT_PROGRESS_PAGE_INTERVAL = 10
COMMENT_RETRY_ATTEMPTS = 3
COMMENT_RETRY_DELAY_SECONDS = 1


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
    content = comment.get("content") or {}
    reply_control = comment.get("reply_control") or {}
    ip_location = normalize_text(reply_control.get("location", ""))

    for prefix in ("IP属地：", "IP属地:"):
        if ip_location.startswith(prefix):
            ip_location = ip_location[len(prefix) :].strip()
            break

    return {
        "rpid": comment.get("rpid"),
        "mid": comment.get("mid"),
        "user_name": normalize_text(member.get("uname", "")),
        "user_level": level_info.get("current_level", 0),
        "message": normalize_text(content.get("message", "")),
        "ctime": comment.get("ctime", 0),
        "like": comment.get("like", 0),
        "reply_count": comment.get("count", 0),
        "state": comment.get("state", 0),
        "ip_location": ip_location,
        "image_urls": parse_image_urls(content),
    }


def request_comment_page(
    oid,
    page_cursor,
    cookie,
    mixin_key,
    mode,
    page_size,
):
    """使用游标请求一页一级评论。"""
    params = {
        "oid": oid,
        "type": 1,
        "mode": mode,
        "next": page_cursor.get("next", 0),
        "ps": page_size,
        "pagination_str": json.dumps(
            {"offset": page_cursor.get("offset", "")},
            separators=(",", ":"),
        ),
        "plat": 1,
        "web_location": COMMENT_WEB_LOCATION,
    }

    return request_wbi_json(
        "/x/v2/reply/wbi/main",
        params,
        cookie,
        mixin_key,
    )


def request_comment_page_with_retry(
    oid,
    page_cursor,
    cookie,
    mixin_key,
    mode,
    page_size,
):
    """请求评论页，并在失败时短暂重试。"""
    for attempt in range(1, COMMENT_RETRY_ATTEMPTS + 1):
        try:
            return request_comment_page(
                oid,
                page_cursor,
                cookie,
                mixin_key,
                mode,
                page_size,
            )
        except RuntimeError:
            if attempt == COMMENT_RETRY_ATTEMPTS:
                raise

            time.sleep(COMMENT_RETRY_DELAY_SECONDS)

    raise RuntimeError("请求评论页失败")


def extract_page_comments(data, include_top=False):
    """提取当前页的一级评论并转换成轻量记录。"""
    replies = []

    if include_top:
        replies.extend(data.get("top_replies") or [])

    replies.extend(data.get("replies") or [])
    return [parse_comment(comment) for comment in replies]


def write_comment_rows(path, rows):
    """合并并重新写入评论 CSV。"""
    temp_path = path.with_name(f"{path.name}.tmp")
    write_csv(temp_path, COMMENT_COLUMNS, rows)
    temp_path.replace(path)


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
        key=lambda row: int(row.get("ctime") or 0),
        reverse=True,
    )
    return merged


class CommentCrawler:
    """按 WBI 游标分页顺序采集视频的全部一级评论。"""

    def __init__(
        self,
        session,
        mode=COMMENT_MODE_TIME,
        page_size=COMMENT_PAGE_SIZE,
    ):
        self.session = session
        self.mode = int(mode)
        self.page_size = min(
            max(1, int(page_size)),
            COMMENT_MAX_PAGE_SIZE,
        )

        if self.mode not in {COMMENT_MODE_TIME, COMMENT_MODE_HOT}:
            raise ValueError("评论模式只能是 2（时间）或 3（热门）")

    def run(self):
        oid = self.session.video_info.get("aid")

        if not oid:
            raise RuntimeError(f"视频 {self.session.bvid} 没有返回 aid")

        video_dir = self.session.video_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / f"comments_{self.session.bvid}.csv"
        page_cursor = {}
        page_number = 0
        total_reply_count = 0
        collected_rows = []
        seen_rpids = set()

        mode_name = "热门评论" if self.mode == COMMENT_MODE_HOT else "时间顺序"
        print(f"开始完整采集评论：{output_path}")
        print(f"评论模式：{mode_name}，每页 {self.page_size} 条")
        print("开始采集评论，使用 WBI 游标分页")

        while True:
            data = request_comment_page_with_retry(
                oid,
                page_cursor,
                self.session.cookie,
                self.session.mixin_key,
                self.mode,
                self.page_size,
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

            page_cursor = {
                "next": cursor.get("next", 0),
                "offset": next_offset,
            }

        saved_rows = merge_comment_rows(collected_rows)
        write_comment_rows(output_path, saved_rows)
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
    parser.add_argument(
        "--mode",
        choices=("time", "hot"),
        default="time",
        help="评论排序：time 按时间，hot 按热门",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=COMMENT_PAGE_SIZE,
        help="评论每页数量，最大 30",
    )
    args = parser.parse_args()

    ensure_login()
    CommentCrawler(
        VideoSession(args.bvid),
        mode=COMMENT_MODE_HOT if args.mode == "hot" else COMMENT_MODE_TIME,
        page_size=args.page_size,
    ).run()


if __name__ == "__main__":
    main()
