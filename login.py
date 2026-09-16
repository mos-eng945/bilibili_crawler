"""
Bilibili 登录状态管理。

整体思路：
1. 使用 bilibili_state.json 保存 Playwright 的 Cookie 和 localStorage。
2. 本地检查 SESSDATA 是否存在且未过期。
3. 请求 nav 接口，确认登录状态在服务端仍然有效。
4. 没有有效状态时打开浏览器，等待人工登录后重新保存。
"""

import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent

# 登录状态保存的文件名
STATE_FILE = BASE_DIR / "bilibili_state.json"


# =========================
# 1. 读取登录状态
# =========================
def load_state():
    """读取 bilibili_state.json，失败返回 None"""
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        print("登录状态文件已损坏，需要重新登录")
        return None


def get_cookie_header(state=None):
    """读取登录状态并生成请求 Cookie，也可以直接传入 state。"""
    if state is None:
        state = load_state()

    if not state:
        raise RuntimeError("没有可用的登录状态，请先运行 login.py")

    return "; ".join(
        f'{cookie["name"]}={cookie["value"]}'
        for cookie in state.get("cookies", [])
    )


# =========================
# 2. 检查本地 cookie
# =========================
def has_cookie():
    """检查本地是否有未过期的 SESSDATA 登录 cookie"""
    state = load_state()

    if state is None:
        return False

    for cookie in state.get("cookies", []):
        if cookie.get("name") != "SESSDATA":
            continue

        expires = cookie.get("expires", -1)

        # expires 为 -1 表示会话 cookie，大于 0 时是 Unix 时间戳
        if expires and expires > 0 and expires < time.time():
            print("登录 cookie 已过期，需要重新登录")
            return False

        return True

    return False


# =========================
# 3. 联网验证 cookie
# =========================
def check_login_online():
    """请求 nav 接口，确认 cookie 在服务端仍然有效"""
    state = load_state()

    if state is None:
        return False

    cookie_header = get_cookie_header(state)

    request = urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.load(response)
    except (OSError, json.JSONDecodeError):
        # 网络异常时不强制重新登录，交给后面的流程自己判断
        print("无法验证登录状态（网络问题），先按已登录处理")
        return True

    return data.get("data", {}).get("isLogin") is True


# =========================
# 4. 手动登录
# =========================
def login():
    """打开浏览器，人工登录，然后把 cookie 存到 STATE_FILE"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")

        context = browser.new_context()

        page = context.new_page()

        page.goto("https://www.bilibili.com/")

        print("请在浏览器中手动登录 Bilibili")
        input("登录完成后按回车...")

        # 保存登录状态
        context.storage_state(path=STATE_FILE)

        print("登录状态已经保存")

        browser.close()


# =========================
# 5. 统一入口
# =========================
def ensure_login():
    """有可用 cookie 就跳过登录，否则弹出浏览器手动登录"""
    if not has_cookie():
        login()
        return

    if check_login_online():
        print("检测到有效登录状态，跳过登录")
        return

    print("cookie 已失效，重新登录")
    login()


# 单独运行本文件时只做登录这一件事：python login.py
if __name__ == "__main__":
    ensure_login()
