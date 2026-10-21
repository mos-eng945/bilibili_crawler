"""Import danmaku, comments and AI subtitles from per-video folders."""

import csv
import json
from datetime import datetime
from pathlib import Path

from db import get_connection


DANMAKU_FIELDS = [
    "id",
    "bvid",
    "time_text",
    "time_seconds",
    "weight",
    "content",
    "hash",
    "send_time",
    "pool",
]

COMMENT_FIELDS = [
    "rpid",
    "bvid",
    "mid",
    "user_name",
    "user_level",
    "sex",
    "vip",
    "message",
    "ctime_text",
    "ctime",
    "like_count",
    "reply_count",
    "state",
    "ip_location",
    "image_urls",
]


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def hms_to_seconds(value):
    parts = str(value or "").split(":")
    if len(parts) != 3:
        return 0
    try:
        hours, minutes, seconds = map(int, parts)
    except ValueError:
        return 0
    return hours * 3600 + minutes * 60 + seconds


def extract_bvid(folder):
    name = folder.name
    if name.startswith("BV") and "_" in name:
        return name.split("_", 1)[0]
    return name


def import_danmaku(path, bvid, cursor):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            danmaku_id = to_int(row.get("弹幕id") or row.get("id"))
            if not danmaku_id:
                continue

            time_text = row.get("出现时间") or row.get("time_text") or ""
            values = {
                "id": danmaku_id,
                "bvid": bvid,
                "time_text": time_text,
                "time_seconds": hms_to_seconds(time_text),
                "weight": to_int(row.get("权重") or row.get("weight")),
                "content": row.get("内容") or row.get("content") or "",
                "hash": row.get("哈希") or row.get("hash") or "",
                "send_time": parse_datetime(row.get("发送时间") or row.get("send_time")),
                "pool": to_int(row.get("弹幕池") or row.get("pool")),
            }

            columns = ", ".join(DANMAKU_FIELDS)
            placeholders = ", ".join(["%s"] * len(DANMAKU_FIELDS))
            updates = ", ".join(
                [f"{name} = new.{name}" for name in DANMAKU_FIELDS if name != "id"]
            )
            sql = (
                f"INSERT INTO danmaku ({columns}) VALUES ({placeholders}) "
                f"AS new ON DUPLICATE KEY UPDATE {updates}"
            )
            cursor.execute(sql, [values[name] for name in DANMAKU_FIELDS])


def import_comments(path, bvid, cursor):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rpid = to_int(row.get("rpid"))
            if not rpid:
                continue

            ctime_text = row.get("ctime_text") or ""
            values = {
                "rpid": rpid,
                "bvid": bvid,
                "mid": to_int(row.get("mid")),
                "user_name": row.get("user_name") or "",
                "user_level": to_int(row.get("user_level")),
                "sex": row.get("sex") or "",
                "vip": to_int(row.get("vip")),
                "message": row.get("message") or "",
                "ctime_text": ctime_text,
                "ctime": parse_datetime(ctime_text),
                "like_count": to_int(row.get("like") or row.get("like_count")),
                "reply_count": to_int(row.get("reply_count")),
                "state": to_int(row.get("state")),
                "ip_location": row.get("ip_location") or "",
                "image_urls": row.get("image_urls") or "",
            }

            columns = ", ".join(COMMENT_FIELDS)
            placeholders = ", ".join(["%s"] * len(COMMENT_FIELDS))
            updates = ", ".join(
                [f"{name} = new.{name}" for name in COMMENT_FIELDS if name != "rpid"]
            )
            sql = (
                f"INSERT INTO comments ({columns}) VALUES ({placeholders}) "
                f"AS new ON DUPLICATE KEY UPDATE {updates}"
            )
            cursor.execute(sql, [values[name] for name in COMMENT_FIELDS])


def import_subtitle(path, bvid, cursor):
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    cid = to_int(data.get("cid"))
    page = to_int(data.get("page"))
    body = data.get("subtitle", {}).get("body", [])

    for item in body:
        start_time = float(item.get("from", 0) or 0)
        content = item.get("content") or ""
        if not content:
            continue

        cursor.execute(
            """
            INSERT INTO subtitles (bvid, cid, page, start_time, end_time, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new
            ON DUPLICATE KEY UPDATE
                end_time = new.end_time,
                content = new.content
            """,
            (
                bvid,
                cid,
                page,
                start_time,
                float(item.get("to", 0) or 0),
                content,
            ),
        )


def import_video_folder(folder, cursor):
    bvid = extract_bvid(folder)

    for path in folder.glob("danmaku_*.csv"):
        import_danmaku(path, bvid, cursor)

    for path in folder.glob("comments_*.csv"):
        import_comments(path, bvid, cursor)

    for path in folder.glob("subtitle_*.json"):
        import_subtitle(path, bvid, cursor)


def import_all(output_dir):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            video_root = output_dir / "video"
            if not video_root.is_dir():
                return

            for folder in video_root.iterdir():
                if folder.is_dir():
                    import_video_folder(folder, cursor)

        connection.commit()
    finally:
        connection.close()


def main():
    from config import OUTPUT_DIR
    import_all(OUTPUT_DIR)
    print("Danmaku, comments and subtitles import finished.")


if __name__ == "__main__":
    main()

