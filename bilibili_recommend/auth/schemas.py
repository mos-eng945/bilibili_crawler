"""Request and response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError


USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


def validate_username(value):
    if not USERNAME_PATTERN.fullmatch(value):
        raise PydanticCustomError(
            "username_format",
            "用户名必须为 3 到 20 位，以字母开头，只能包含字母、数字和下划线",
        )
    return value


def validate_password(value):
    if not 8 <= len(value) <= 64:
        raise PydanticCustomError("password_length", "密码长度必须为 8 到 64 位")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise PydanticCustomError("password_format", "密码必须同时包含字母和数字")
    return value


class RegisterRequest(BaseModel):
    username: str
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def check_rules(self):
        validate_username(self.username)
        validate_password(self.password)
        if self.confirm_password != self.password:
            raise PydanticCustomError("confirm_password_mismatch", "两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    avatar: str = Field(min_length=1, max_length=512)


class FavoriteRequest(BaseModel):
    bvid: str = Field(min_length=1, max_length=32)


class UserOut(BaseModel):
    username: str
    avatar: str
    created_at: str

