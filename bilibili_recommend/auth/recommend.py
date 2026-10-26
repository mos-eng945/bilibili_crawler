"""Recommendation, category and video endpoints."""

import math
from datetime import datetime
from pathlib import Path

import pymysql
import yaml
import jieba
from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import MYSQL_CONFIG
import security


router = APIRouter(prefix="/api", tags=["recommend"])
optional_bearer_scheme = HTTPBearer(auto_error=False)

CATEGORIES_FILE = Path(__file__).resolve().parents[1] / "config" / "categories.yaml"


class Weights(BaseModel):
    semantic_similarity: float = Field(
        0.3, ge=0, le=1, description="语义相似度权重"
    )
    popularity: float = Field(0.1, ge=0, le=1, description="基础热度权重")
    sentiment: float = Field(0.3, ge=0, le=1, description="弹幕情感权重")
    comment_quality: float = Field(
        0.3, ge=0, le=1, description="评论质量权重"
    )


class RecommendRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="用户输入的关键词或标签",
    )
    category_id: str | None = Field(
        None,
        description="可选，指定学习方向分类 ID",
    )
    limit: int = Field(10, ge=1, le=50, description="返回视频数量")
    page: int = Field(1, ge=1, description="页码")
    weights: Weights = Weights()


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def get_optional_user_id(credentials: HTTPAuthorizationCredentials | None):
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    try:
        payload = security.decode_access_token(token)
    except Exception:
        return None

    username = payload.get("sub")
    if not username:
        return None

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    return row[0] if row else None


def serialize_value(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def tokenize(text):
    return " ".join(jieba.lcut((text or "").lower()))


def load_categories():
    data = yaml.safe_load(CATEGORIES_FILE.read_text(encoding="utf-8"))
    return data["categories"], data.get("thresholds", {})


def classify_query(query, categories):
    targets = []
    for category in categories:
        if category.get("id") == "other":
            continue
        text = " ".join(
            [category.get("name", ""), category.get("description", "")]
            + (category.get("keywords") or [])
        )
        targets.append((category, text))

    if not targets:
        return {"id": "other", "name": "其他学习"}, 0.0, []

    corpus = [tokenize(query)] + [tokenize(text) for _, text in targets]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    scored = []
    for (category, _), similarity in zip(targets, similarities):
        keywords = category.get("keywords") or []
        hits = sum(1 for word in keywords if word.lower() in query.lower())
        keyword_score = min(hits / 5.0, 1.0)
        score = 0.5 * float(similarity) + 0.5 * keyword_score
        scored.append((category, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def classify_result(query, categories, thresholds):
    scored = classify_query(query, categories)
    if not scored:
        return {
            "id": "other",
            "name": "其他学习",
            "confidence": 0.0,
            "level": "low",
        }, []

    top_category, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    diff = top_score - second_score
    high_diff = float(thresholds.get("high_confidence_diff", 0.25))
    low_score = float(thresholds.get("low_confidence_score", 0.30))

    if diff > high_diff:
        level = "high"
    elif top_score >= low_score:
        level = "medium"
    else:
        level = "low"

    result = {
        "id": top_category.get("id"),
        "name": top_category.get("name"),
        "confidence": round(top_score, 4),
        "level": level,
    }
    candidates = [
        {"id": cat.get("id"), "name": cat.get("name")}
        for cat, _ in scored[:3]
    ]
    return result, candidates


def load_videos():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    v.bvid, v.title, u.up_name, v.cover_url,
                    v.view_count, v.like_count, v.favorite_count,
                    COALESCE(vt.video_text, ''),
                    COALESCE(s.popularity, 0.0),
                    COALESCE(s.sentiment, 0.5),
                    COALESCE(s.comment_quality, 0.5)
                FROM videos v
                LEFT JOIN up_info u ON u.mid = v.mid
                LEFT JOIN video_texts vt ON vt.bvid = v.bvid
                LEFT JOIN video_scores s ON s.bvid = v.bvid
                """
            )
            rows = cursor.fetchall()

            cursor.execute("SELECT bvid, category_id FROM video_categories")
            category_rows = cursor.fetchall()
    finally:
        connection.close()

    category_map = {}
    for bvid, category_id in category_rows:
        category_map.setdefault(bvid, []).append(category_id)

    videos = []
    for row in rows:
        videos.append(
            {
                "bvid": row[0],
                "title": row[1],
                "up_name": row[2],
                "cover_url": row[3],
                "view_count": row[4],
                "like_count": row[5],
                "favorite_count": row[6],
                "video_text": row[7],
                "popularity": float(row[8]),
                "sentiment": float(row[9]),
                "comment_quality": float(row[10]),
                "categories": category_map.get(row[0], []),
            }
        )
    return videos


@router.get("/categories")
def get_categories():
    categories, _ = load_categories()
    return {
        "categories": [
            {
                "id": category.get("id"),
                "name": category.get("name"),
                "description": category.get("description", ""),
            }
            for category in categories
        ]
    }


@router.get("/videos")
def list_videos(
    category_id: str | None = Query(None, description="学习方向分类 ID，可选"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页视频数量"),
    sort_by: str = Query("score", description="排序方式：score、view、time"),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            category_filter = ""
            params = []
            if category_id:
                category_filter = (
                    "AND v.bvid IN ("
                    "SELECT bvid FROM video_categories WHERE category_id = %s"
                    ")"
                )
                params.append(category_id)

            cursor.execute(
                f"SELECT COUNT(*) FROM videos v WHERE 1 = 1 {category_filter}",
                params,
            )
            total = cursor.fetchone()[0]

            order_map = {
                "score": "COALESCE(s.popularity, 0) DESC",
                "view": "v.view_count DESC",
                "time": "v.published_at DESC",
            }
            order_by = order_map.get(sort_by, order_map["score"])

            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT v.bvid, v.title, u.up_name, v.cover_url, v.view_count,
                       COALESCE(s.popularity, 0) AS score
                FROM videos v
                LEFT JOIN up_info u ON u.mid = v.mid
                LEFT JOIN video_scores s ON s.bvid = v.bvid
                WHERE 1 = 1 {category_filter}
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    videos = [
        {
            "bvid": row[0],
            "title": row[1],
            "up_name": row[2],
            "cover_url": row[3],
            "view_count": row[4],
            "score": round(float(row[5]), 4),
        }
        for row in rows
    ]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "videos": videos,
    }


@router.get("/up/{mid}/videos")
def list_up_videos(mid: int = ApiPath(description="UP 主 MID")):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT up_name FROM up_info WHERE mid = %s",
                (mid,),
            )
            up_row = cursor.fetchone()

            cursor.execute(
                """
                SELECT v.bvid, v.title, v.cover_url, v.view_count,
                       COALESCE(s.popularity, 0) AS score
                FROM videos v
                LEFT JOIN video_scores s ON s.bvid = v.bvid
                WHERE v.mid = %s
                ORDER BY v.view_count DESC
                """,
                (mid,),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    return {
        "mid": mid,
        "up_name": up_row[0] if up_row else "",
        "videos": [
            {
                "bvid": row[0],
                "title": row[1],
                "cover_url": row[2],
                "view_count": row[3],
                "score": round(float(row[4]), 4),
            }
            for row in rows
        ],
    }


@router.post("/recommend")
def recommend(
    payload: RecommendRequest,
    credentials: HTTPAuthorizationCredentials = Depends(optional_bearer_scheme),
):
    categories, thresholds = load_categories()

    if payload.category_id:
        category = {"id": payload.category_id, "name": payload.category_id}
        candidates = [{"id": payload.category_id, "name": payload.category_id}]
    else:
        category, candidates = classify_result(
            payload.query, categories, thresholds
        )

    user_id = get_optional_user_id(credentials)
    if user_id:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO search_history (user_id, keyword, category_id)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, payload.query, category.get("id", "")),
                )
            connection.commit()
        finally:
            connection.close()

    videos = load_videos()
    target_category = category.get("id")

    if target_category and target_category != "other":
        videos = [video for video in videos if target_category in video["categories"]]

    if not videos:
        videos = load_videos()

    texts = [video["video_text"] or video["title"] for video in videos]
    corpus = [tokenize(payload.query)] + [tokenize(text) for text in texts]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    results = []
    for video, similarity in zip(videos, similarities):
        w = payload.weights
        score = (
            w.semantic_similarity * float(similarity)
            + w.popularity * video["popularity"]
            + w.sentiment * video["sentiment"]
            + w.comment_quality * video["comment_quality"]
        )
        results.append(
            {
                "bvid": video["bvid"],
                "title": video["title"],
                "up_name": video["up_name"],
                "cover_url": video["cover_url"],
                "score": round(score, 4),
                "detail": {
                    "similarity": round(float(similarity), 4),
                    "popularity": round(video["popularity"], 4),
                    "sentiment": round(video["sentiment"], 4),
                    "comment_quality": round(video["comment_quality"], 4),
                },
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    start = (payload.page - 1) * payload.limit
    end = start + payload.limit

    return {
        "category": category,
        "candidates": candidates,
        "recommendations": results[start:end],
    }


@router.get("/videos/{bvid}")
def get_video(bvid: str = ApiPath(description="视频 BV 号")):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM videos WHERE bvid = %s", (bvid,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="视频不存在")

            columns = [column[0] for column in cursor.description]
            video = dict(zip(columns, row))

            cursor.execute(
                "SELECT up_name FROM up_info WHERE mid = %s",
                (video.get("mid", 0),),
            )
            up_row = cursor.fetchone()

            cursor.execute(
                "SELECT tag FROM video_tags WHERE bvid = %s",
                (bvid,),
            )
            tags = [item[0] for item in cursor.fetchall()]
    finally:
        connection.close()

    video = {key: serialize_value(value) for key, value in video.items()}
    video["up_name"] = up_row[0] if up_row else ""
    video["tags"] = tags
    return video


@router.get("/videos/{bvid}/comments")
def get_video_comments(
    bvid: str = ApiPath(description="视频 BV 号"),
    cursor: int = Query(0, ge=0, description="分页游标，传上一次返回的 next_cursor"),
    limit: int = Query(20, ge=1, le=100, description="返回评论数量"),
):
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM comments_clean
                WHERE bvid = %s AND rpid > %s
                ORDER BY rpid
                LIMIT %s
                """,
                (bvid, cursor, limit),
            )
            rows = cur.fetchall()
            columns = [column[0] for column in cur.description]
    finally:
        connection.close()

    comments = [
        {
            column: serialize_value(value)
            for column, value in zip(columns, row)
        }
        for row in rows
    ]
    next_cursor = comments[-1]["rpid"] if len(comments) == limit else None
    return {"items": comments, "next_cursor": next_cursor}


@router.get("/videos/{bvid}/danmaku")
def get_video_danmaku(
    bvid: str = ApiPath(description="视频 BV 号"),
    cursor: int = Query(0, ge=0, description="分页游标，传上一次返回的 next_cursor"),
    limit: int = Query(50, ge=1, le=200, description="返回弹幕数量"),
):
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM danmaku_clean
                WHERE bvid = %s AND id > %s
                ORDER BY id
                LIMIT %s
                """,
                (bvid, cursor, limit),
            )
            rows = cur.fetchall()
            columns = [column[0] for column in cur.description]
    finally:
        connection.close()

    danmaku = [
        {
            column: serialize_value(value)
            for column, value in zip(columns, row)
        }
        for row in rows
    ]
    next_cursor = danmaku[-1]["id"] if len(danmaku) == limit else None
    return {"items": danmaku, "next_cursor": next_cursor}


@router.get("/videos/{bvid}/subtitles")
def get_video_subtitles(bvid: str = ApiPath(description="视频 BV 号")):
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM subtitles
                WHERE bvid = %s
                ORDER BY cid, page, start_time
                """,
                (bvid,),
            )
            rows = cur.fetchall()
            columns = [column[0] for column in cur.description]
    finally:
        connection.close()

    subtitles = [
        {
            column: serialize_value(value)
            for column, value in zip(columns, row)
        }
        for row in rows
    ]
    return {"items": subtitles}


@router.get("/videos/{bvid}/analysis")
def get_video_analysis(bvid: str = ApiPath(description="视频 BV 号")):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(popularity, 0.0),
                       COALESCE(sentiment, 0.5),
                       COALESCE(comment_quality, 0.5),
                       danmaku_count, comment_count, subtitle_count,
                       keywords, category_hint
                FROM video_scores
                WHERE bvid = %s
                """,
                (bvid,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="视频分析数据不存在")
    finally:
        connection.close()

    keywords = [word for word in (row[6] or "").split(",") if word]
    return {
        "bvid": bvid,
        "popularity": float(row[0]),
        "sentiment": float(row[1]),
        "comment_quality": float(row[2]),
        "danmaku_count": row[3],
        "comment_count": row[4],
        "subtitle_count": row[5],
        "keywords": [{"word": word, "weight": 0.0} for word in keywords],
        "category_hint": row[7],
    }

