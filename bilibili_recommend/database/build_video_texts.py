"""Build the video_texts table used for TF-IDF similarity."""

import sys
from pathlib import Path

import pymysql


sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MYSQL_CONFIG  # noqa: E402


VIDEO_TEXTS_DDL = """
CREATE TABLE IF NOT EXISTS video_texts (
    bvid       VARCHAR(32) PRIMARY KEY,
    video_text TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def main():
    connection = pymysql.connect(**MYSQL_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(VIDEO_TEXTS_DDL)
            cursor.execute("TRUNCATE TABLE video_texts")

            cursor.execute(
                "SELECT bvid, title, description FROM videos"
            )
            videos = cursor.fetchall()

            inserted = 0
            for bvid, title, description in videos:
                cursor.execute(
                    "SELECT tag FROM video_tags WHERE bvid = %s",
                    (bvid,),
                )
                tags = [row[0] for row in cursor.fetchall()]

                cursor.execute(
                    "SELECT keywords FROM video_scores WHERE bvid = %s",
                    (bvid,),
                )
                keyword_row = cursor.fetchone()
                keywords = keyword_row[0] if keyword_row else ""

                parts = [title or "", description or "", " ".join(tags), keywords or ""]
                video_text = " ".join(part for part in parts if part).strip()

                cursor.execute(
                    """
                    INSERT INTO video_texts (bvid, video_text)
                    VALUES (%s, %s)
                    """,
                    (bvid, video_text),
                )
                inserted += 1

        connection.commit()
    finally:
        connection.close()

    print(f"video_texts 已生成 {inserted} 条")


if __name__ == "__main__":
    main()

