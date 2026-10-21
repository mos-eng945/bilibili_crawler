"""FastAPI auth backend."""

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import database
import security
from config import DEFAULT_AVATAR
from schemas import LoginRequest, ProfileUpdate, RegisterRequest, UserOut


app = FastAPI(title="Bilibili Learning Auth")

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
            "SELECT username, avatar, created_at FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="用户不存在")

    return {
        "username": row[0],
        "avatar": row[1],
        "created_at": row[2],
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

