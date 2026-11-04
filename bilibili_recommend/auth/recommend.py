"""Recommendation, category and video endpoints."""

import math
from datetime import datetime
from pathlib import Path
from typing import Literal

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

# 分类列表使用的全局综合分，不含用户输入相似度。
GLOBAL_SCORE_SQL = (
    "(0.4 * COALESCE(s.popularity, 0.0) "
    "+ 0.3 * COALESCE(s.sentiment, 0.5) "
    "+ 0.3 * COALESCE(s.comment_quality, 0.5))"
)


class Weights(BaseModel):
    """推荐综合分的四项权重配置。"""

    semantic_similarity: float = Field(
        0.3, ge=0, le=1, description="语义相似度权重", examples=[0.3]
    )
    popularity: float = Field(0.1, ge=0, le=1, description="基础热度权重", examples=[0.1])
    sentiment: float = Field(0.3, ge=0, le=1, description="弹幕情感权重", examples=[0.3])
    comment_quality: float = Field(
        0.3, ge=0, le=1, description="评论质量权重", examples=[0.3]
    )


class RecommendFilters(BaseModel):
    """推荐结果的筛选和排序条件。"""

    duration_min: int | None = Field(
        None,
        ge=0,
        description="最小视频时长，单位秒",
        examples=[300],
    )
    duration_max: int | None = Field(
        None,
        ge=0,
        description="最大视频时长，单位秒",
        examples=[1800],
    )
    sort_by: Literal["score", "view", "time"] = Field(
        "score",
        description="排序方式：score、view、time",
        examples=["score"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "duration_min": 300,
                "duration_max": 1800,
                "sort_by": "score",
            }
        }
    }


class RecommendRequest(BaseModel):
    """推荐接口请求体。"""

    query: str = Field(
        min_length=1,
        max_length=200,
        description="用户输入的关键词或标签",
        examples=["想学 Python 爬虫"],
    )
    category_id: str | None = Field(
        None,
        description="可选，指定学习方向分类 ID",
        examples=["programming"],
    )
    limit: int = Field(10, ge=1, le=50, description="返回视频数量", examples=[10])
    page: int = Field(1, ge=1, description="页码", examples=[1])
    weights: Weights = Weights()
    filters: RecommendFilters = RecommendFilters()

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "想学 Python 爬虫",
                "category_id": None,
                "limit": 10,
                "page": 1,
                "weights": {
                    "semantic_similarity": 0.3,
                    "popularity": 0.1,
                    "sentiment": 0.3,
                    "comment_quality": 0.3,
                },
                "filters": {
                    "duration_min": None,
                    "duration_max": None,
                    "sort_by": "score",
                },
            }
        }
    }


def get_connection():
    """创建并返回一个 MySQL 连接。"""
    return pymysql.connect(**MYSQL_CONFIG)


def get_optional_user_id(credentials: HTTPAuthorizationCredentials | None):
    """尝试解析可选 Bearer Token，返回用户 ID；没有或无效时返回 None。"""
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
    """把 datetime 值转成统一字符串，其他值原样返回。"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def tokenize(text):
    """使用 jieba 分词并用空格连接，供 TF-IDF 使用。"""
    return " ".join(jieba.lcut((text or "").lower()))


def load_categories():
    """读取学习方向分类和置信度阈值配置。"""
    data = yaml.safe_load(CATEGORIES_FILE.read_text(encoding="utf-8"))
    return data["categories"], data.get("thresholds", {})


def classify_query(query, categories):
    """把用户输入和分类文本比较，返回按分数降序的分类列表。"""
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
    """根据分类分数差和阈值，判断高、中、低置信度。"""
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
    """从数据库加载推荐所需的视频、UP 主、文本、评分和分类信息。"""
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
                    COALESCE(s.comment_quality, 0.5),
                    v.duration_seconds,
                    v.published_at
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
                "duration_seconds": int(row[11] or 0),
                "published_at": row[12],
                "categories": category_map.get(row[0], []),
            }
        )
    return videos


@router.get(
    "/categories",
    summary="获取学习方向分类",
    description="返回所有学习方向分类。",
    responses={
        200: {
            "description": "分类列表",
            "content": {
                "application/json": {
                    "example": {
                        "categories": [
                            {
                                "id": "programming",
                                "name": "编程开发",
                                "description": "编程语言、软件开发等课程",
                            }
                        ]
                    }
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "page"],
                                "msg": "页码必须大于等于 1",
                                "type": "greater_than_equal",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_categories():
    """返回所有学习方向分类。"""
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


@router.get(
    "/videos",
    summary="获取分类视频列表",
    description="按分类、分页和排序返回视频列表。",
    responses={
        200: {
            "description": "视频列表",
            "content": {
                "application/json": {
                    "example": {
                        "total": 120,
                        "page": 1,
                        "page_size": 20,
                        "videos": [
                            {
                                "bvid": "BV1GJ411x7h7",
                                "title": "Python 爬虫入门",
                                "up_name": "某 UP 主",
                                "cover_url": "https://example.com/cover.jpg",
                                "view_count": 10000,
                                "score": 0.78,
                            }
                        ],
                    }
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "mid"],
                                "msg": "字段应为整数",
                                "type": "int_parsing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def list_videos(
    category_id: str | None = Query(
        None,
        description="学习方向分类 ID，可选",
        example="programming",
    ),
    page: int = Query(1, ge=1, description="页码，从 1 开始", example=1),
    page_size: int = Query(20, ge=1, le=100, description="每页视频数量", example=20),
    sort_by: str = Query(
        "score",
        description="排序方式：score、view、time",
        example="score",
    ),
):
    """按分类、分页和排序返回视频列表。"""
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
                "score": f"{GLOBAL_SCORE_SQL} DESC",
                "view": "v.view_count DESC",
                "time": "v.published_at DESC",
            }
            order_by = order_map.get(sort_by, order_map["score"])

            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT v.bvid, v.title, u.up_name, v.cover_url, v.view_count,
                       {GLOBAL_SCORE_SQL} AS score
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


@router.get(
    "/up/{mid}/videos",
    summary="获取 UP 主视频列表",
    description="返回指定 UP 主发布的视频列表。",
    responses={
        200: {
            "description": "UP 主视频列表",
            "content": {
                "application/json": {
                    "example": {
                        "mid": 456828781,
                        "up_name": "某 UP 主",
                        "videos": [
                            {
                                "bvid": "BV1GJ411x7h7",
                                "title": "视频标题",
                                "cover_url": "https://example.com/cover.jpg",
                                "view_count": 10000,
                                "score": 0.78,
                            }
                        ],
                    }
                }
            },
        },
        400: {
            "description": "请求参数错误",
            "content": {
                "application/json": {
                    "example": {"detail": "duration_min 不能大于 duration_max"}
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "query"],
                                "msg": "字段必填",
                                "type": "missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def list_up_videos(
    mid: int = ApiPath(description="UP 主 MID", example=456828781)
):
    """返回指定 UP 主的视频列表。"""
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


@router.post(
    "/recommend",
    summary="推荐学习视频",
    description="根据用户输入识别学习方向，返回按综合评分排序的视频列表。",
    responses={
        200: {
            "description": "推荐结果",
            "content": {
                "application/json": {
                    "example": {
                        "category": {
                            "id": "programming",
                            "name": "编程开发",
                            "confidence": 0.82,
                            "level": "high",
                        },
                        "candidates": [
                            {"id": "programming", "name": "编程开发"},
                            {"id": "ai_data", "name": "人工智能与数据"},
                        ],
                        "recommendations": [
                            {
                                "bvid": "BV1GJ411x7h7",
                                "title": "Python 爬虫入门",
                                "up_name": "某 UP 主",
                                "cover_url": "https://example.com/cover.jpg",
                                "score": 0.78,
                                "detail": {
                                    "similarity": 0.32,
                                    "popularity": 0.71,
                                    "sentiment": 0.55,
                                    "comment_quality": 0.61,
                                },
                            }
                        ],
                    }
                }
            },
        },
        404: {
            "description": "视频不存在",
            "content": {"application/json": {"example": {"detail": "视频不存在"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "bvid"],
                                "msg": "字段必填",
                                "type": "missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def recommend(
    payload: RecommendRequest,
    credentials: HTTPAuthorizationCredentials = Depends(optional_bearer_scheme),
):
    """根据用户输入识别学习方向，返回综合评分排序后的视频列表。"""
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

    filters = payload.filters
    if (
        filters.duration_min is not None
        and filters.duration_max is not None
        and filters.duration_min > filters.duration_max
    ):
        raise HTTPException(status_code=400, detail="duration_min 不能大于 duration_max")

    if filters.duration_min is not None:
        videos = [
            video
            for video in videos
            if video.get("duration_seconds", 0) >= filters.duration_min
        ]

    if filters.duration_max is not None:
        videos = [
            video
            for video in videos
            if video.get("duration_seconds", 0) <= filters.duration_max
        ]

    texts = [video["video_text"] or video["title"] for video in videos]
    corpus = [tokenize(payload.query)] + [tokenize(text) for text in texts]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    scored_results = []
    for video, similarity in zip(videos, similarities):
        w = payload.weights
        score = (
            w.semantic_similarity * float(similarity)
            + w.popularity * video["popularity"]
            + w.sentiment * video["sentiment"]
            + w.comment_quality * video["comment_quality"]
        )
        scored_results.append(
            (
                score,
                video.get("view_count", 0),
                video.get("published_at") or "",
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
                },
            )
        )

    if filters.sort_by == "view":
        scored_results.sort(key=lambda item: item[1], reverse=True)
    elif filters.sort_by == "time":
        scored_results.sort(key=lambda item: item[2], reverse=True)
    else:
        scored_results.sort(key=lambda item: item[0], reverse=True)

    results = [item[3] for item in scored_results]
    start = (payload.page - 1) * payload.limit
    end = start + payload.limit

    return {
        "category": category,
        "candidates": candidates,
        "recommendations": results[start:end],
    }


@router.get(
    "/videos/{bvid}",
    summary="获取视频详情",
    description="返回单个视频的详情、UP 主信息和标签。",
    responses={
        200: {
            "description": "视频详情",
            "content": {
                "application/json": {
                    "example": {
                        "bvid": "BV1GJ411x7h7",
                        "title": "视频标题",
                        "description": "视频简介",
                        "up_name": "某 UP 主",
                        "cover_url": "https://example.com/cover.jpg",
                        "tags": ["Python", "教程"],
                    }
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "limit"],
                                "msg": "数值必须在 1 到 100 之间",
                                "type": "less_than_equal",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_video(
    bvid: str = ApiPath(description="视频 BV 号", example="BV1GJ411x7h7")
):
    """返回单个视频的详情、UP 主信息和标签。"""
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


@router.get(
    "/videos/{bvid}/comments",
    summary="获取视频评论",
    description="按游标分页返回视频评论。",
    responses={
        200: {
            "description": "评论列表",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "rpid": 1,
                                "bvid": "BV1GJ411x7h7",
                                "message": "讲得很清楚",
                            }
                        ],
                        "next_cursor": 2,
                    }
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "limit"],
                                "msg": "数值必须在 1 到 200 之间",
                                "type": "less_than_equal",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_video_comments(
    bvid: str = ApiPath(description="视频 BV 号", example="BV1GJ411x7h7"),
    cursor: int = Query(
        0,
        ge=0,
        description="分页游标，传上一次返回的 next_cursor",
        example=0,
    ),
    limit: int = Query(20, ge=1, le=100, description="返回评论数量", example=20),
):
    """按游标分页返回视频评论。"""
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM comments
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


@router.get(
    "/videos/{bvid}/danmaku",
    summary="获取视频弹幕",
    description="按游标分页返回视频弹幕。",
    responses={
        200: {
            "description": "弹幕列表",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 1,
                                "bvid": "BV1GJ411x7h7",
                                "content": "学到了",
                            }
                        ],
                        "next_cursor": 2,
                    }
                }
            },
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "bvid"],
                                "msg": "字段必填",
                                "type": "missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_video_danmaku(
    bvid: str = ApiPath(description="视频 BV 号", example="BV1GJ411x7h7"),
    cursor: int = Query(
        0,
        ge=0,
        description="分页游标，传上一次返回的 next_cursor",
        example=0,
    ),
    limit: int = Query(50, ge=1, le=200, description="返回弹幕数量", example=50),
):
    """按游标分页返回视频弹幕。"""
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM danmaku
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


@router.get(
    "/videos/{bvid}/subtitles",
    summary="获取视频字幕",
    description="返回视频的全部分段字幕。",
    responses={
        200: {
            "description": "字幕列表",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 1,
                                "bvid": "BV1GJ411x7h7",
                                "language": "ai-zh",
                                "content": "大家好",
                            }
                        ]
                    }
                }
            },
        },
        404: {
            "description": "视频分析数据不存在",
            "content": {"application/json": {"example": {"detail": "视频分析数据不存在"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "bvid"],
                                "msg": "字段必填",
                                "type": "missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_video_subtitles(
    bvid: str = ApiPath(description="视频 BV 号", example="BV1GJ411x7h7")
):
    """返回视频的全部分段字幕。"""
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


@router.get(
    "/videos/{bvid}/analysis",
    summary="获取视频分析结果",
    description="返回视频的评分、计数、关键词和分类提示。",
    responses={
        200: {
            "description": "视频分析结果",
            "content": {
                "application/json": {
                    "example": {
                        "bvid": "BV1GJ411x7h7",
                        "popularity": 0.78,
                        "sentiment": 0.55,
                        "comment_quality": 0.61,
                        "danmaku_count": 500,
                        "comment_count": 120,
                        "subtitle_count": 300,
                        "keywords": [{"word": "函数", "weight": 0.0}],
                        "category_hint": "编程开发",
                    }
                }
            },
        }
    },
)
def get_video_analysis(
    bvid: str = ApiPath(description="视频 BV 号", example="BV1GJ411x7h7")
):
    """返回视频的评分、计数、关键词和分类提示。"""
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

