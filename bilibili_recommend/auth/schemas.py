"""Request and response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError


USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


def validate_username(value):
    """校验用户名格式：3 到 20 位，以字母开头，仅允许字母、数字和下划线。"""
    if not USERNAME_PATTERN.fullmatch(value):
        raise PydanticCustomError(
            "username_format",
            "用户名必须为 3 到 20 位，以字母开头，只能包含字母、数字和下划线",
        )
    return value


def validate_password(value):
    """校验密码长度和字符组成：8 到 64 位，且必须同时包含字母和数字。"""
    if not 8 <= len(value) <= 64:
        raise PydanticCustomError("password_length", "密码长度必须为 8 到 64 位")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise PydanticCustomError("password_format", "密码必须同时包含字母和数字")
    return value


class RegisterRequest(BaseModel):
    """注册接口请求体，包含用户名、密码和确认密码。"""

    username: str = Field(
        description="用户名，3 到 20 位，以字母开头，只能包含字母、数字和下划线",
        examples=["zhangsan"],
    )
    password: str = Field(
        description="密码，8 到 64 位，必须同时包含字母和数字",
        examples=["abc12345"],
    )
    confirm_password: str = Field(
        description="再次输入密码，需要与密码一致",
        examples=["abc12345"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "zhangsan",
                "password": "abc12345",
                "confirm_password": "abc12345",
            }
        }
    }

    @model_validator(mode="after")
    def check_rules(self):
        validate_username(self.username)
        validate_password(self.password)
        if self.confirm_password != self.password:
            raise PydanticCustomError("confirm_password_mismatch", "两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    """登录接口请求体。"""

    username: str = Field(description="登录用户名", examples=["zhangsan"])
    password: str = Field(description="登录密码", examples=["abc12345"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "zhangsan",
                "password": "abc12345",
            }
        }
    }


class ProfileUpdate(BaseModel):
    """用户资料更新请求体，当前只允许修改头像地址。"""

    avatar: str = Field(
        min_length=1,
        max_length=512,
        description="新的头像 URL 地址",
        examples=["https://example.com/avatar.png"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "avatar": "https://example.com/avatar.png",
            }
        }
    }


class FavoriteRequest(BaseModel):
    """收藏请求体，只包含要收藏的视频 BV 号。"""

    bvid: str = Field(
        min_length=1,
        max_length=32,
        description="要收藏的视频 BV 号",
        examples=["BV1GJ411x7h7"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "bvid": "BV1GJ411x7h7",
            }
        }
    }


class UserOut(BaseModel):
    """用户信息响应体。"""

    username: str
    avatar: str
    created_at: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "zhangsan",
                "avatar": "https://example.com/default-avatar.png",
                "created_at": "2026-10-21 10:00:00",
            }
        }
    }

