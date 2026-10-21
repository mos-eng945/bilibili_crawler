"""Request and response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


def validate_username(value):
    if not USERNAME_PATTERN.fullmatch(value):
        raise ValueError(
            "用户名必须为 3 到 20 位，以字母开头，只能包含字母、数字和下划线"
        )
    return value


def validate_password(value):
    if not 8 <= len(value) <= 64:
        raise ValueError("密码长度必须为 8 到 64 位")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("密码必须同时包含字母和数字")
    return value


class RegisterRequest(BaseModel):
    username: str
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def check_username(cls, value):
        return validate_username(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value):
        return validate_password(value)

    @field_validator("confirm_password")
    @classmethod
    def check_confirm_password(cls, value, info):
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("两次输入的密码不一致")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    avatar: str = Field(min_length=1, max_length=512)


class UserOut(BaseModel):
    username: str
    avatar: str
    created_at: str

