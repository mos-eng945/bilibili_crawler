"""FastAPI auth backend."""

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import database
import recommend
import security
from config import DEFAULT_AVATAR
from schemas import (
    FavoriteRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    UserOut,
)


app = FastAPI(title="Bilibili Learning Auth")
app.include_router(recommend.router)
bearer_scheme = HTTPBearer(auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """提供一个 MySQL 连接，请求结束后自动关闭。"""
    connection = database.get_connection()
    try:
        yield connection
    finally:
        connection.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    connection=Depends(get_db),
):
    """从 Bearer Token 中解析当前登录用户，未认证时返回 401。"""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未登录")

    token = credentials.credentials
    try:
        payload = security.decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录已过期") from exc

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="登录已过期")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, username, avatar, created_at FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="用户不存在")

    return {
        "id": row[0],
        "username": row[1],
        "avatar": row[2],
        "created_at": row[3],
    }


def lock_seconds(fail_count):
    """根据连续登录失败次数计算账号锁定秒数。"""
    if fail_count < 5:
        return 0
    exponent = (fail_count - 5) // 2
    return min(30 * (2**exponent), 1800)


@app.on_event("startup")
def on_startup():
    """应用启动时创建认证和用户功能所需的数据表。"""
    database.ensure_tables()


@app.get(
    "/api/health",
    summary="健康检查",
    description="返回后端服务是否正常运行的简单状态。",
    responses={
        200: {
            "description": "服务正常",
            "content": {"application/json": {"example": {"status": "ok"}}},
        }
    },
)
def health():
    """健康检查接口，用于确认后端服务是否正常运行。"""
    return {"status": "ok"}


@app.post(
    "/api/auth/register",
    status_code=201,
    summary="注册账号",
    description="创建新用户，保存密码哈希，并返回 JWT Token。",
    responses={
        201: {
            "description": "注册成功",
            "content": {
                "application/json": {
                    "example": {
                        "message": "注册成功",
                        "token": "JWT Token",
                        "user": {
                            "username": "zhangsan",
                            "avatar": "https://example.com/default-avatar.png",
                        },
                    }
                }
            },
        },
        409: {
            "description": "用户名已存在",
            "content": {"application/json": {"example": {"detail": "用户名已存在"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "username"],
                                "msg": "用户名格式不正确",
                                "type": "value_error",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def register(payload: RegisterRequest, connection=Depends(get_db)):
    """注册新用户：检查用户名唯一，保存密码哈希，并签发 JWT。"""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (payload.username,),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="用户名已存在")

        password_hash = security.hash_password(payload.password)
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, avatar)
            VALUES (%s, %s, %s)
            """,
            (payload.username, password_hash, DEFAULT_AVATAR),
        )
    connection.commit()

    token = security.create_access_token(payload.username)
    return {
        "message": "注册成功",
        "token": token,
        "user": {
            "username": payload.username,
            "avatar": DEFAULT_AVATAR,
        },
    }


@app.post(
    "/api/auth/login",
    summary="登录账号",
    description="校验用户名和密码，登录成功后返回 JWT Token。",
    responses={
        200: {
            "description": "登录成功",
            "content": {
                "application/json": {
                    "example": {
                        "message": "登录成功",
                        "token": "JWT Token",
                        "user": {"username": "zhangsan", "avatar": "https://example.com/default-avatar.png"},
                    }
                }
            },
        },
        400: {
            "description": "用户名或密码错误",
            "content": {"application/json": {"example": {"detail": "用户名或密码错误"}}},
        },
        429: {
            "description": "尝试次数过多，账号暂时锁定",
            "content": {"application/json": {"example": {"detail": "尝试次数过多，请稍后再试"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "password"],
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
def login(payload: LoginRequest, connection=Depends(get_db)):
    """登录用户，并处理失败次数统计和账号锁定。"""
    now = datetime.now()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fail_count, locked_until FROM login_attempts WHERE username = %s",
            (payload.username,),
        )
        attempt = cursor.fetchone()

        fail_count = attempt[0] if attempt else 0
        locked_until = attempt[1] if attempt else None

        if locked_until and locked_until > now:
            raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")

        cursor.execute(
            "SELECT username, password_hash, avatar, created_at "
            "FROM users WHERE username = %s",
            (payload.username,),
        )
        user = cursor.fetchone()

        password_ok = bool(
            user and security.verify_password(payload.password, user[1])
        )

        if not password_ok:
            fail_count += 1
            duration = lock_seconds(fail_count)
            locked_until = now + timedelta(seconds=duration) if duration else None
            cursor.execute(
                """
                INSERT INTO login_attempts (username, fail_count, locked_until)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    fail_count = VALUES(fail_count),
                    locked_until = VALUES(locked_until)
                """,
                (payload.username, fail_count, locked_until),
            )
            connection.commit()
            if locked_until:
                raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")
            raise HTTPException(status_code=400, detail="用户名或密码错误")

        cursor.execute(
            """
            INSERT INTO login_attempts (username, fail_count, locked_until)
            VALUES (%s, 0, NULL)
            ON DUPLICATE KEY UPDATE
                fail_count = 0,
                locked_until = NULL
            """,
            (payload.username,),
        )
    connection.commit()

    token = security.create_access_token(user[0])
    return {
        "message": "登录成功",
        "token": token,
        "user": {
            "username": user[0],
            "avatar": user[2],
        },
    }


@app.post(
    "/api/auth/logout",
    summary="退出登录",
    description="返回退出成功；JWT 无状态，实际由前端删除 Token。",
    responses={
        200: {
            "description": "退出成功",
            "content": {"application/json": {"example": {"message": "已退出登录"}}},
        }
    },
)
def logout():
    """退出登录。JWT 无状态，实际由前端删除 Token。"""
    # JWT 是无状态的，登出由前端删除 Token 完成。
    return {"message": "已退出登录"}


@app.get(
    "/api/user/profile",
    response_model=UserOut,
    summary="获取当前用户资料",
    description="返回当前登录用户的用户名、头像和创建时间。",
    responses={
        200: {
            "description": "当前用户资料",
            "content": {
                "application/json": {
                    "example": {
                        "username": "zhangsan",
                        "avatar": "https://example.com/default-avatar.png",
                        "created_at": "2026-10-21 10:00:00",
                    }
                }
            },
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
    },
)
def get_profile(user=Depends(get_current_user)):
    """返回当前登录用户的基本资料。"""
    created_at = user["created_at"]
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "username": user["username"],
        "avatar": user["avatar"],
        "created_at": str(created_at),
    }


@app.put(
    "/api/user/profile",
    response_model=UserOut,
    summary="更新当前用户资料",
    description="更新当前登录用户资料，目前只支持修改头像。",
    responses={
        200: {
            "description": "更新后的用户资料",
            "content": {
                "application/json": {
                    "example": {
                        "username": "zhangsan",
                        "avatar": "https://example.com/avatar.png",
                        "created_at": "2026-10-21 10:00:00",
                    }
                }
            },
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "avatar"],
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
def update_profile(
    payload: ProfileUpdate,
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """更新当前用户资料，目前仅支持修改头像。"""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET avatar = %s WHERE username = %s",
            (payload.avatar, user["username"]),
        )
        cursor.execute(
            "SELECT username, avatar, created_at FROM users WHERE username = %s",
            (user["username"],),
        )
        row = cursor.fetchone()
    connection.commit()

    created_at = row[2]
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "username": row[0],
        "avatar": row[1],
        "created_at": str(created_at),
    }


@app.post(
    "/api/user/favorites",
    status_code=201,
    summary="收藏视频",
    description="把指定视频加入当前用户的收藏列表，重复收藏不会报错。",
    responses={
        201: {
            "description": "收藏成功",
            "content": {"application/json": {"example": {"message": "收藏成功"}}},
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
        422: {
            "description": "请求参数校验失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "bvid"],
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
def add_favorite(
    payload: FavoriteRequest,
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """收藏指定视频；重复收藏不会报错。"""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO favorites (user_id, bvid) VALUES (%s, %s)",
            (user["id"], payload.bvid),
        )
    connection.commit()
    return {"message": "收藏成功"}


@app.get(
    "/api/user/favorites",
    summary="获取收藏列表",
    description="返回当前用户收藏的视频列表。",
    responses={
        200: {
            "description": "收藏视频列表",
            "content": {
                "application/json": {
                    "example": {
                        "favorites": [
                            {
                                "bvid": "BV1GJ411x7h7",
                                "title": "视频标题",
                                "up_name": "UP 主",
                                "cover_url": "https://example.com/cover.jpg",
                                "favorited_at": "2026-10-21 10:00:00",
                            }
                        ]
                    }
                }
            },
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
    },
)
def get_favorites(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """查询当前用户收藏的视频列表。"""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT f.bvid, v.title, u.up_name, v.cover_url, f.created_at
            FROM favorites f
            JOIN videos v ON v.bvid = f.bvid
            LEFT JOIN up_info u ON u.mid = v.mid
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
            """,
            (user["id"],),
        )
        rows = cursor.fetchall()

    favorites = []
    for row in rows:
        created_at = row[4]
        if hasattr(created_at, "strftime"):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
        favorites.append(
            {
                "bvid": row[0],
                "title": row[1],
                "up_name": row[2],
                "cover_url": row[3],
                "favorited_at": str(created_at),
            }
        )
    return {"favorites": favorites}


@app.delete(
    "/api/user/favorites/{bvid}",
    summary="取消收藏",
    description="从当前用户的收藏列表中删除指定视频。",
    responses={
        200: {
            "description": "取消成功",
            "content": {"application/json": {"example": {"message": "已取消收藏"}}},
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
    },
)
def remove_favorite(
    bvid: str = Path(description="要取消收藏的视频 BV 号", example="BV1GJ411x7h7"),
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """取消当前用户对指定视频的收藏。"""
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = %s AND bvid = %s",
            (user["id"], bvid),
        )
    connection.commit()
    return {"message": "已取消收藏"}


@app.get(
    "/api/user/search_history",
    summary="获取搜索历史",
    description="返回当前用户最近 100 条搜索历史。",
    responses={
        200: {
            "description": "搜索历史列表",
            "content": {
                "application/json": {
                    "example": {
                        "history": [
                            {
                                "keyword": "Python",
                                "category_id": "programming",
                                "created_at": "2026-10-21 10:00:00",
                            }
                        ]
                    }
                }
            },
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
    },
)
def get_search_history(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """查询当前用户最近的 100 条搜索历史。"""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT keyword, category_id, created_at
            FROM search_history
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 100
            """,
            (user["id"],),
        )
        rows = cursor.fetchall()

    history = []
    for row in rows:
        created_at = row[2]
        if hasattr(created_at, "strftime"):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
        history.append(
            {
                "keyword": row[0],
                "category_id": row[1],
                "created_at": str(created_at),
            }
        )
    return {"history": history}


@app.delete(
    "/api/user/search_history",
    summary="清空搜索历史",
    description="删除当前用户的全部搜索历史。",
    responses={
        200: {
            "description": "清空成功",
            "content": {"application/json": {"example": {"message": "已清空搜索历史"}}},
        },
        401: {
            "description": "未登录",
            "content": {"application/json": {"example": {"detail": "未登录"}}},
        },
    },
)
def clear_search_history(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    """清空当前用户的搜索历史。"""
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM search_history WHERE user_id = %s",
            (user["id"],),
        )
    connection.commit()
    return {"message": "已清空搜索历史"}

