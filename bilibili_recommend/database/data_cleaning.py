"""Clean raw danmaku and comments tables into *_clean tables."""

import re

import pymysql

from config import MYSQL_CONFIG


SPAM_WORDS = [
    "http",
    "https",
    "加微信",
    "加群",
    "微信",
    "公众号",
    "广告",
    "兼职",
    "刷单",
    "代练",
]


def has_meaningful_chars(text):
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def is_spam(text):
    return any(word in text for word in SPAM_WORDS)


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def clean_danmaku_text(content):
    text = normalize_text(content)
    if not text:
        return None
    if not has_meaningful_chars(text):
        return None
    if is_spam(text):
        return None
    return text


def clean_comment_text(message):
    text = normalize_text(message)
    if not text:
        return None
    if is_spam(text):
        return None
    return text


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def main():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS danmaku_clean LIKE danmaku")
            cursor.execute("CREATE TABLE IF NOT EXISTS comments_clean LIKE comments")
            cursor.execute("TRUNCATE TABLE danmaku_clean")
            cursor.execute("TRUNCATE TABLE comments_clean")

            cursor.execute(
                """
                SELECT id, bvid, time_text, time_seconds, weight, content,
                       hash, send_time, pool
                FROM danmaku
                """
            )
            danmaku_rows = cursor.fetchall()

            seen_danmaku = set()
            inserted_danmaku = 0
            for row in danmaku_rows:
                cleaned = clean_danmaku_text(row[5])
                if cleaned is None:
                    continue
                key = (row[1], cleaned)
                if key in seen_danmaku:
                    continue
                seen_danmaku.add(key)
                cursor.execute(
                    """
                    INSERT INTO danmaku_clean (
                        id, bvid, time_text, time_seconds, weight, content,
                        hash, send_time, pool
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (row[0], row[1], row[2], row[3], row[4], cleaned, row[6], row[7], row[8]),
                )
                inserted_danmaku += 1

            cursor.execute(
                """
                SELECT rpid, bvid, mid, user_name, user_level, sex, vip,
                       message, ctime_text, ctime, like_count, reply_count,
                       state, ip_location, image_urls
                FROM comments
                """
            )
            comment_rows = cursor.fetchall()

            seen_comments = set()
            inserted_comments = 0
            for row in comment_rows:
                cleaned = clean_comment_text(row[7])
                if cleaned is None:
                    continue
                key = (row[2], cleaned)
                if key in seen_comments:
                    continue
                seen_comments.add(key)
                cursor.execute(
                    """
                    INSERT INTO comments_clean (
                        rpid, bvid, mid, user_name, user_level, sex, vip,
                        message, ctime_text, ctime, like_count, reply_count,
                        state, ip_location, image_urls
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                        cleaned, row[8], row[9], row[10], row[11], row[12], row[13], row[14],
                    ),
                )
                inserted_comments += 1

        connection.commit()
        print(f"danmaku 原始 {len(danmaku_rows)} 条，清洗后 {inserted_danmaku} 条")
        print(f"comments 原始 {len(comment_rows)} 条，清洗后 {inserted_comments} 条")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

