"""Import video metadata, up info and tags from crawler output."""

import csv
import json
from datetime import datetime
from pathlib import Path

from db import get_connection


VIDEO_FIELDS = [
    "bvid",
    "title",
    "description",
    "mid",
    "published_at",
    "duration_seconds",
    "tid",
    "partition_name",
    "cover_url",
    "view_count",
    "like_count",
    "coin_count",
    "favorite_count",
    "share_count",
    "reply_count",
    "danmaku_count",
]

UP_FIELDS = ["mid", "up_name", "face_url", "follower_count"]


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


def split_tags(value):
    if not value:
        return []
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]


def normalize_list_row(row):
    """Normalize one search/up CSV row."""
    bvid = (row.get("bvid") or "").strip()
    if not bvid:
        return None

    mid = to_int(row.get("mid"))
    up_name = row.get("author") or row.get("up_name") or ""

    video = {
        "bvid": bvid,
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "mid": mid,
        "published_at": parse_datetime(row.get("published_at")),
        "duration_seconds": to_int(row.get("duration_seconds")),
        "tid": to_int(row.get("tid")),
        "partition_name": row.get("partition") or "",
        "cover_url": row.get("cover_url") or "",
        "view_count": to_int(row.get("play_count") or row.get("view_count")),
        "like_count": to_int(row.get("like") or row.get("like_count")),
        "coin_count": to_int(row.get("coin") or row.get("coin_count")),
        "favorite_count": to_int(
            row.get("favorite_count") or row.get("favorite")
        ),
        "share_count": to_int(row.get("share_count") or row.get("share")),
        "reply_count": to_int(
            row.get("comment_count") or row.get("reply_count") or row.get("reply")
        ),
        "danmaku_count": to_int(
            row.get("danmaku_count") or row.get("danmaku")
        ),
    }

    up = {
        "mid": mid,
        "up_name": up_name,
        "face_url": row.get("up_face") or "",
        "follower_count": to_int(
            row.get("author_follower_count")
            or row.get("up_follower_count")
            or row.get("follower_count")
        ),
    }

    tags = split_tags(row.get("tags"))
    return video, up, tags


def normalize_info_row(data):
    """Normalize one video_info.json object."""
    bvid = (data.get("bvid") or "").strip()
    if not bvid:
        return None

    mid = to_int(data.get("mid"))

    video = {
        "bvid": bvid,
        "title": data.get("title") or "",
        "description": data.get("description") or "",
        "mid": mid,
        "published_at": parse_datetime(data.get("published_at")),
        "duration_seconds": to_int(data.get("duration_seconds")),
        "tid": to_int(data.get("tid")),
        "partition_name": data.get("partition") or "",
        "cover_url": data.get("cover_url") or "",
        "view_count": to_int(data.get("view")),
        "like_count": to_int(data.get("like")),
        "coin_count": to_int(data.get("coin")),
        "favorite_count": to_int(data.get("favorite")),
        "share_count": to_int(data.get("share")),
        "reply_count": to_int(data.get("reply")),
        "danmaku_count": to_int(data.get("danmaku")),
    }

    up = {
        "mid": mid,
        "up_name": data.get("up_name") or "",
        "face_url": data.get("up_face") or "",
        "follower_count": to_int(data.get("up_follower_count")),
    }

    return video, up, []


def upsert_video(cursor, video):
    columns = ", ".join(video)
    placeholders = ", ".join(["%s"] * len(video))
    updates = ", ".join([f"{name} = new.{name}" for name in video if name != "bvid"])
    sql = (
        f"INSERT INTO videos ({columns}) VALUES ({placeholders}) "
        f"AS new ON DUPLICATE KEY UPDATE {updates}"
    )
    cursor.execute(sql, [video[name] for name in video])


def upsert_up(cursor, up):
    columns = ", ".join(UP_FIELDS)
    placeholders = ", ".join(["%s"] * len(UP_FIELDS))
    updates = ", ".join([f"{name} = new.{name}" for name in UP_FIELDS if name != "mid"])
    sql = (
        f"INSERT INTO up_info ({columns}) VALUES ({placeholders}) "
        f"AS new ON DUPLICATE KEY UPDATE {updates}"
    )
    cursor.execute(sql, [up[name] for name in UP_FIELDS])


def upsert_tags(cursor, bvid, tags):
    for tag in tags:
        cursor.execute(
            "INSERT IGNORE INTO video_tags (bvid, tag) VALUES (%s, %s)",
            (bvid, tag),
        )


def import_list_csv(path, cursor):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = normalize_list_row(row)
            if not normalized:
                continue
            video, up, tags = normalized
            upsert_video(cursor, video)
            if up["mid"]:
                upsert_up(cursor, up)
            upsert_tags(cursor, video["bvid"], tags)


def import_video_info(path, cursor):
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    normalized = normalize_info_row(data)
    if not normalized:
        return

    video, up, _ = normalized
    upsert_video(cursor, video)
    if up["mid"]:
        upsert_up(cursor, up)


def import_all(output_dir):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            list_files = []
            for pattern in ("search_*.csv", "videos_*.csv"):
                list_files.extend(output_dir.rglob(pattern))

            for path in list_files:
                import_list_csv(path, cursor)

            for path in output_dir.rglob("video_info.json"):
                import_video_info(path, cursor)

        connection.commit()
    finally:
        connection.close()


def main():
    from config import OUTPUT_DIR
    import_all(OUTPUT_DIR)
    print("Video metadata import finished.")


if __name__ == "__main__":
    main()

