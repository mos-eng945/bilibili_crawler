"""Analyze all videos stored in MySQL and persist reusable scores."""

import math
import statistics
import sys
from collections import Counter
from pathlib import Path

import pymysql


DATABASE_DIR = Path(__file__).resolve().parents[1] / "database"
sys.path.insert(0, str(DATABASE_DIR))

from config import MYSQL_CONFIG  # noqa: E402


STOPWORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们",
    "这", "那", "就", "都", "也", "还", "有", "没", "在", "上", "下", "不",
    "一个", "这个", "那个", "什么", "怎么", "为什么", "因为", "所以", "然后",
    "如果", "可以", "就是", "但是", "而且", "自己", "大家", "老师", "同学",
    "这里", "那里", "这样", "那样", "时候", "现在", "已经", "还是",
    "的话", "东西", "比如说", "应该", "其实", "是不是", "那么",
}


POSITIVE_WORDS = {
    "清楚", "明白", "懂了", "听懂", "有用", "详细", "感谢", "谢谢", "厉害",
    "清晰", "通俗", "易懂", "不错", "优秀", "好", "赞", "收藏", "学到了",
}


NEGATIVE_WORDS = {
    "不懂", "没听懂", "看不懂", "模糊", "错误", "不清楚", "废话", "太慢",
    "快进", "啰嗦", "不好", "差", "没用", "失望", "退钱", "别误人",
}


CATEGORY_KEYWORDS = {
    "考研数学 / 高等数学": [
        "函数", "极限", "导数", "微分", "积分", "无穷", "sin", "cos",
        "tan", "lim", "fx", "方程", "求导", "级数",
    ],
    "编程开发": [
        "python", "java", "代码", "编程", "变量", "循环", "函数", "数组",
        "算法", "爬虫", "前端", "后端",
    ],
    "英语学习": [
        "英语", "单词", "语法", "阅读", "作文", "听力", "翻译", "雅思", "托福",
    ],
    "人工智能与数据": [
        "机器学习", "深度学习", "神经网络", "模型", "训练", "数据", "算法",
    ],
    "美食烹饪": [
        "美食", "做饭", "食材", "烹饪", "烘焙", "蛋糕", "炒", "煮", "汤",
    ],
}


VIDEO_SCORES_DDL = """
CREATE TABLE IF NOT EXISTS video_scores (
    bvid            VARCHAR(32) PRIMARY KEY,
    popularity      DECIMAL(8, 5) NULL,
    sentiment       DECIMAL(8, 5) NULL,
    comment_quality DECIMAL(8, 5) NULL,
    danmaku_count   INT DEFAULT 0,
    comment_count   INT DEFAULT 0,
    subtitle_count  INT DEFAULT 0,
    keywords        TEXT NULL,
    category_hint   VARCHAR(64) NULL,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def normalize_popularity(view, like, favorite, danmaku):
    view_score = min(math.log10(view + 1) / 8.0, 1.0) * 100
    like_rate = like / view if view else 0
    favorite_rate = favorite / view if view else 0
    like_score = min(like_rate * 20, 1.0) * 100
    favorite_score = min(favorite_rate * 10, 1.0) * 100
    danmaku_score = min(math.log10(danmaku + 1) / 6.0, 1.0) * 100
    return (
        0.40 * view_score
        + 0.25 * like_score
        + 0.20 * favorite_score
        + 0.15 * danmaku_score
    ) / 100.0


def classify_sentiment(text):
    try:
        from snownlp import SnowNLP

        score = SnowNLP(text).sentiments
    except ImportError:
        positive = sum(1 for word in POSITIVE_WORDS if word in text)
        negative = sum(1 for word in NEGATIVE_WORDS if word in text)
        score = 0.8 if positive > negative else 0.2 if negative > positive else 0.5

    if score >= 0.6:
        label = "positive"
    elif score <= 0.4:
        label = "negative"
    else:
        label = "neutral"
    return label


def analyze_danmaku(bvid, cursor):
    cursor.execute(
        "SELECT content FROM danmaku_clean WHERE bvid = %s",
        (bvid,),
    )
    rows = cursor.fetchall()
    if not rows:
        return None, 0

    counts = Counter(classify_sentiment(row[0] or "") for row in rows)
    total = len(rows)
    positive_ratio = counts["positive"] / total
    negative_ratio = counts["negative"] / total
    sentiment = (positive_ratio - negative_ratio + 1) / 2
    return round(sentiment, 5), total


def comment_quality(message, like_count):
    text = message or ""
    length_score = min(len(text) / 50.0, 1.0)
    like_score = min(like_count / 20.0, 1.0)
    info_words = {
        "为什么", "怎么", "如何", "请问", "建议", "注意", "总结",
        "知识点", "公式", "概念", "讲解", "学到", "推导",
    }
    question_words = {"为什么", "怎么", "如何", "请问", "吗", "?", "？"}
    spam_words = {"加微信", "加群", "QQ", "链接", "http", "广告", "兼职"}

    info_score = 1.0 if any(word in text for word in info_words) else 0.5
    question_score = 1.0 if any(word in text for word in question_words) else 0.0
    spam_penalty = 1.0 if any(word in text for word in spam_words) else 0.0

    score = (
        0.30 * length_score
        + 0.20 * like_score
        + 0.25 * info_score
        + 0.15 * question_score
        - 0.10 * spam_penalty
    )
    return max(0.0, min(score, 1.0))


def analyze_comments(bvid, cursor):
    cursor.execute(
        "SELECT message, like_count FROM comments_clean WHERE bvid = %s",
        (bvid,),
    )
    rows = cursor.fetchall()
    if not rows:
        return None, 0

    scores = [comment_quality(row[0] or "", int(row[1] or 0)) for row in rows]
    return round(statistics.mean(scores), 5), len(rows)


def analyze_subtitles(bvid, cursor):
    cursor.execute(
        "SELECT content FROM subtitles WHERE bvid = %s",
        (bvid,),
    )
    rows = cursor.fetchall()
    if not rows:
        return None, 0, None

    text = "\n".join(row[0] or "" for row in rows)
    try:
        import jieba.analyse

        weighted = jieba.analyse.extract_tags(text, topK=20, withWeight=True)
        keywords = [word for word, _ in weighted if word not in STOPWORDS]
    except ImportError:
        keywords = []

    category_hint = None
    if keywords:
        scores = {}
        for category, words in CATEGORY_KEYWORDS.items():
            hit = sum(1 for keyword in keywords if keyword in words)
            if hit:
                scores[category] = hit
        if scores:
            category_hint = max(scores, key=scores.get)

    return ",".join(keywords[:20]), len(rows), category_hint


def main():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(VIDEO_SCORES_DDL)

            cursor.execute(
                """
                SELECT bvid, view_count, like_count, favorite_count, danmaku_count
                FROM videos
                """
            )
            videos = cursor.fetchall()

            for index, video in enumerate(videos, start=1):
                bvid, view, like, favorite, danmaku = video
                popularity = normalize_popularity(view, like, favorite, danmaku)
                sentiment, danmaku_count = analyze_danmaku(bvid, cursor)
                comment_score, comment_count = analyze_comments(bvid, cursor)
                keywords, subtitle_count, category_hint = analyze_subtitles(
                    bvid, cursor
                )

                cursor.execute(
                    """
                    INSERT INTO video_scores (
                        bvid, popularity, sentiment, comment_quality,
                        danmaku_count, comment_count, subtitle_count,
                        keywords, category_hint
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    AS new
                    ON DUPLICATE KEY UPDATE
                        popularity = new.popularity,
                        sentiment = new.sentiment,
                        comment_quality = new.comment_quality,
                        danmaku_count = new.danmaku_count,
                        comment_count = new.comment_count,
                        subtitle_count = new.subtitle_count,
                        keywords = new.keywords,
                        category_hint = new.category_hint
                    """,
                    (
                        bvid,
                        round(popularity, 5),
                        sentiment,
                        comment_score,
                        danmaku_count,
                        comment_count,
                        subtitle_count,
                        keywords,
                        category_hint,
                    ),
                )

                if index % 10 == 0 or index == len(videos):
                    print(f"已处理 {index}/{len(videos)} 个视频")

        connection.commit()
    finally:
        connection.close()

    print("全库分析完成，结果已写入 video_scores 表。")


if __name__ == "__main__":
    main()

