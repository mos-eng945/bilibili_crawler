"""Assign videos to learning categories and store them in video_categories."""

import sys
from pathlib import Path

import pymysql
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MYSQL_CONFIG  # noqa: E402


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CATEGORIES_FILE = CONFIG_DIR / "categories.yaml"


VIDEO_CATEGORIES_DDL = """
CREATE TABLE IF NOT EXISTS video_categories (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    bvid        VARCHAR(32) NOT NULL,
    category_id VARCHAR(64) NOT NULL,
    score       INT DEFAULT 0,
    UNIQUE KEY uk_bvid_category (bvid, category_id),
    KEY idx_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def load_categories():
    data = yaml.safe_load(CATEGORIES_FILE.read_text(encoding="utf-8"))
    return data["categories"]


def lower_text(value):
    return (value or "").lower()


def build_video_text(video, tags, keywords):
    parts = [
        video.get("title", ""),
        video.get("description", ""),
        video.get("partition_name", ""),
        " ".join(tags),
        keywords or "",
    ]
    return " ".join(part for part in parts if part).lower()


def match_categories(text, partition_name, categories):
    matches = []

    for category in categories:
        category_id = category.get("id", "")
        if category_id == "other":
            continue

        keywords = category.get("keywords") or []
        partitions = category.get("bilibili_partitions") or []

        keyword_hits = sum(1 for word in keywords if lower_text(word) in text)
        partition_hit = 1 if partition_name and partition_name in partitions else 0
        score = keyword_hits + (2 if partition_hit else 0)

        if score > 0:
            matches.append((category_id, score))

    matches.sort(key=lambda item: item[1], reverse=True)
    return matches[:3]


def main():
    categories = load_categories()

    connection = pymysql.connect(**MYSQL_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(VIDEO_CATEGORIES_DDL)
            cursor.execute("TRUNCATE TABLE video_categories")

            cursor.execute(
                """
                SELECT bvid, title, description, partition_name
                FROM videos
                """
            )
            videos = cursor.fetchall()

            assigned = 0
            fallback = 0
            for bvid, title, description, partition_name in videos:
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

                text = build_video_text(
                    {
                        "title": title,
                        "description": description,
                        "partition_name": partition_name,
                    },
                    tags,
                    keywords,
                )

                matches = match_categories(text, partition_name, categories)
                if not matches:
                    matches = [("other", 0)]
                    fallback += 1

                for category_id, score in matches:
                    cursor.execute(
                        """
                        INSERT INTO video_categories (bvid, category_id, score)
                        VALUES (%s, %s, %s)
                        """,
                        (bvid, category_id, score),
                    )
                assigned += 1

        connection.commit()
    finally:
        connection.close()

    print(f"视频总数：{len(videos)}")
    print(f"已分类视频：{assigned}")
    print(f"归入其他学习：{fallback}")


if __name__ == "__main__":
    main()

