"""FastAPI auth backend."""

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    connection = database.get_connection()
    try:
        yield connection
    finally:
        connection.close()


def get_current_user(
    authorization: str = Header(default=""),
    connection=Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = authorization.removeprefix("Bearer ")
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
    if fail_count < 5:
        return 0
    exponent = (fail_count - 5) // 2
    return min(30 * (2**exponent), 1800)


@app.on_event("startup")
def on_startup():
    database.ensure_tables()


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest, connection=Depends(get_db)):
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


@app.post("/api/auth/login")
def login(payload: LoginRequest, connection=Depends(get_db)):
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


@app.post("/api/auth/logout")
def logout():
    # JWT 是无状态的，登出由前端删除 Token 完成。
    return {"message": "已退出登录"}


@app.get("/api/user/profile", response_model=UserOut)
def get_profile(user=Depends(get_current_user)):
    created_at = user["created_at"]
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "username": user["username"],
        "avatar": user["avatar"],
        "created_at": str(created_at),
    }


@app.put("/api/user/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
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


@app.post("/api/user/favorites", status_code=201)
def add_favorite(
    payload: FavoriteRequest,
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO favorites (user_id, bvid) VALUES (%s, %s)",
            (user["id"], payload.bvid),
        )
    connection.commit()
    return {"message": "收藏成功"}


@app.get("/api/user/favorites")
def get_favorites(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
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


@app.delete("/api/user/favorites/{bvid}")
def remove_favorite(
    bvid: str,
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = %s AND bvid = %s",
            (user["id"], bvid),
        )
    connection.commit()
    return {"message": "已取消收藏"}


@app.get("/api/user/search_history")
def get_search_history(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
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


@app.delete("/api/user/search_history")
def clear_search_history(
    user=Depends(get_current_user),
    connection=Depends(get_db),
):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM search_history WHERE user_id = %s",
            (user["id"],),
        )
    connection.commit()
    return {"message": "已清空搜索历史"}

