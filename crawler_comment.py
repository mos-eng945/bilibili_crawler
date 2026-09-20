"""Bilibili 一级评论下载器。"""

import argparse
import csv
import json
import re
import time

from bilibili_api import (
    get_cookie_header,
    get_video_dir,
    get_video_info,
    get_wbi_mixin_key,
    request_wbi_json,
)
from login import ensure_login
from main import DEFAULT_BVID

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
    "image_urls",
]
COMMENT_MODE_TIME = 2
COMMENT_PAGE_SIZE = 30
COMMENT_WEB_LOCATION = 1315875
COMMENT_PROGRESS_PAGE_INTERVAL = 10
COMMENT_RETRY_ATTEMPTS = 3
COMMENT_RETRY_DELAY_SECONDS = 1
COMMENT_CHECKPOINT_VERSION = 1


def parse_image_urls(content):
    """提取评论图片地址，不下载图片。"""
    urls = []

    for item in content.get("pictures") or []:
        url = item.get("img_src") or ""

        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("http://"):
            url = f"https://{url[7:]}"

        if url:
            urls.append(url)

    return urls


def normalize_text(value):
    """把评论文本规范成适合 CSV 的单行内容。"""
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n+", r"\\n", text)
    return text.strip()


def parse_comment(comment):
    """把评论接口数据转换成轻量记录。"""
    member = comment.get("member") or {}
    level_info = member.get("level_info") or {}
    content = comment.get("content") or {}

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
        "image_urls": parse_image_urls(content),
    }


def request_comment_page(oid, page_cursor, cookie, mixin_key):
    """使用游标请求一页一级评论。"""
    params = {
        "oid": oid,
        "type": 1,
        "mode": COMMENT_MODE_TIME,
        "next": page_cursor.get("next", 0),
        "ps": COMMENT_PAGE_SIZE,
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


def request_comment_page_with_retry(oid, page_cursor, cookie, mixin_key):
    """请求评论页，并在失败时短暂重试。"""
    for attempt in range(1, COMMENT_RETRY_ATTEMPTS + 1):
        try:
            return request_comment_page(
                oid,
                page_cursor,
                cookie,
                mixin_key,
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


def read_comment_rows(path):
    """读取已经保存的评论 CSV。"""
    if not path.exists():
        return []

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def append_comment_rows(path, rows):
    """把新评论追加到 CSV，并在新文件时写入表头。"""
    write_header = not path.exists() or path.stat().st_size == 0

    with open(path, "a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COMMENT_COLUMNS)

        if write_header:
            writer.writeheader()

        if rows:
            writer.writerows(rows)


def write_comment_rows(path, rows):
    """合并并重新写入评论 CSV。"""
    temp_path = path.with_name(f"{path.name}.tmp")

    with open(temp_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COMMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

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


def load_comment_checkpoint(path):
    """读取评论采集断点，内容无效时返回空字典。"""
    if not path.exists():
        return {}

    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if checkpoint.get("version") != COMMENT_CHECKPOINT_VERSION:
        return {}

    return checkpoint


def save_comment_checkpoint(path, checkpoint):
    """原子写入评论采集断点。"""
    temp_path = path.with_name(f"{path.name}.tmp")
    content = json.dumps(checkpoint, ensure_ascii=False, indent=2)
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def crawl_comments(
    bvid=DEFAULT_BVID,
    workers=None,
):
    """增量或断点采集视频的一级评论并保存为 CSV。"""
    if workers is not None:
        print("游标分页需要顺序请求，workers 参数不再生效")

    cookie = get_cookie_header()
    video_info = get_video_info(bvid, cookie)
    oid = video_info.get("aid")

    if not oid:
        raise RuntimeError(f"视频 {bvid} 没有返回 aid")

    mixin_key = get_wbi_mixin_key(cookie)
    video_dir = get_video_dir(video_info)
    video_dir.mkdir(parents=True, exist_ok=True)
    output_path = video_dir / f"comments_{bvid}.csv"
    checkpoint_path = video_dir / f"comments_{bvid}.checkpoint.json"
    existing_rows = read_comment_rows(output_path)
    checkpoint = load_comment_checkpoint(checkpoint_path)
    resumed = bool(checkpoint and existing_rows)

    if resumed:
        page_cursor = {
            "next": checkpoint.get("next", 0),
            "offset": checkpoint.get("offset", ""),
        }
        page_number = int(checkpoint.get("page", 0))
        total_reply_count = int(checkpoint.get("total_reply_count", 0))
        incremental = bool(checkpoint.get("incremental"))
        print(
            f"检测到断点，从第 {page_number + 1} 页继续，"
            f"当前已保存 {len(existing_rows)} 条一级评论"
        )
    else:
        checkpoint_path.unlink(missing_ok=True)
        page_cursor = {}
        page_number = 0
        total_reply_count = 0
        incremental = bool(existing_rows)

    seen_rpids = {
        str(row.get("rpid") or "")
        for row in existing_rows
        if row.get("rpid")
    }

    if resumed:
        print(
            f"继续{'增量' if incremental else '全量'}采集："
            f"{output_path}"
        )
    elif incremental:
        print(f"检测到已有评论，执行增量采集：{output_path}")
    else:
        print(f"未发现完整记录，执行全量采集：{output_path}")

    print("开始采集评论，使用 WBI 游标分页")

    while True:
        data = request_comment_page_with_retry(
            oid,
            page_cursor,
            cookie,
            mixin_key,
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

        append_comment_rows(output_path, new_rows)

        cursor = data.get("cursor") or {}
        total_reply_count = cursor.get("all_count") or total_reply_count
        is_end = bool(cursor.get("is_end"))
        next_offset = (
            cursor.get("pagination_reply") or {}
        ).get("next_offset")
        reached_existing = incremental and bool(page_comments) and not new_rows

        save_comment_checkpoint(
            checkpoint_path,
            {
                "version": COMMENT_CHECKPOINT_VERSION,
                "bvid": bvid,
                "page": page_number,
                "next": cursor.get("next", 0),
                "offset": next_offset or "",
                "total_reply_count": total_reply_count,
                "incremental": incremental,
            },
        )

        if (
            page_number == 1
            or page_number % COMMENT_PROGRESS_PAGE_INTERVAL == 0
            or is_end
            or reached_existing
        ):
            print(
                f"已获取第 {page_number} 页，"
                f"新增 {len(new_rows)} 条，"
                f"累计 {len(seen_rpids)} 条；"
                f"视频总评论 {total_reply_count} 条（含子评论）"
            )

        if is_end or not next_offset or reached_existing:
            break

        page_cursor = {
            "next": cursor.get("next", 0),
            "offset": next_offset,
        }

    if incremental:
        write_comment_rows(
            output_path,
            merge_comment_rows(read_comment_rows(output_path)),
        )

    checkpoint_path.unlink(missing_ok=True)
    saved_count = len(read_comment_rows(output_path))

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
        "--workers",
        type=int,
        default=None,
        help="兼容旧参数；WBI 游标分页需要顺序请求",
    )
    args = parser.parse_args()

    ensure_login()
    crawl_comments(args.bvid, workers=args.workers)


if __name__ == "__main__":
    main()
