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

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from config import BASE_DIR

# 登录状态保存的文件名
STATE_FILE = BASE_DIR / "bilibili_state.json"

BROWSER_CHANNELS = (
    ("chrome", "Google Chrome"),
    ("msedge", "Microsoft Edge"),
)


def launch_browser(playwright, headless=False):
    """优先使用本机浏览器，缺失时回退到 Playwright Chromium。"""
    for channel, label in BROWSER_CHANNELS:
        try:
            browser = playwright.chromium.launch(
                headless=headless,
                channel=channel,
            )
        except PlaywrightError:
            continue

        print(f"使用 {label} 启动浏览器")
        return browser

    try:
        browser = playwright.chromium.launch(headless=headless)
    except PlaywrightError as exc:
        raise RuntimeError(
            "未找到可用浏览器。请安装 Google Chrome 或 Microsoft Edge，"
            "或运行 `python -m playwright install chromium` 安装 "
            "Playwright 自带浏览器。"
        ) from exc

    print("使用 Playwright Chromium 启动浏览器")
    return browser


# =========================
# 1. 读取登录状态
# =========================
def load_state():
    """读取 bilibili_state.json，失败返回 None"""
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        print("登录状态文件已损坏，需要重新登录")
        return None

    print("成功读取登录状态文件:", STATE_FILE)
    return state


def get_cookie_header(state):
    """把登录状态里的 cookies 拼成 HTTP 请求头需要的 Cookie 头。"""
    if not state:
        raise RuntimeError("没有可用的登录状态，请先运行 login.py")

    # 把 cookies 列表拼成 HTTP 请求头需要的 "name=value; name=value" 格式
    return "; ".join(
        f'{cookie["name"]}={cookie["value"]}' for cookie in state.get("cookies", [])
    )


# =========================
# 2. 检查本地 cookie
# =========================
def has_cookie(state):
    """检查本地是否有未过期的 SESSDATA 登录 cookie"""
    if not state:
        return False

    for cookie in state.get("cookies", []):
        if cookie.get("name") != "SESSDATA":
            continue

        expires = cookie.get("expires", -1)

        # expires 为 -1 表示会话 cookie，大于 0 时是 Unix 时间戳
        if expires and expires > 0 and expires < time.time():
            print("登录 cookie 已过期，需要重新登录")
            return False
        print("登陆有效")
        return True

    return False


# =========================
# 3. 联网验证 cookie
# =========================
def check_login_online(state):
    """请求 nav 接口，确认 cookie 在服务端仍然有效"""
    if not state:
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
            print("登录状态验证结果验证成功")
    except (OSError, json.JSONDecodeError):
        # 网络异常时不强制重新登录，交给后面的流程自己判断
        print("无法验证登录状态（网络问题），先按已登录处理")
        return True

    return data.get("data", {}).get("isLogin") is True


# =========================
# 4. 手动登录
# =========================
def login():
    """打开浏览器，人工登录，验证有效后把 cookie 存到 STATE_FILE"""
    with sync_playwright() as p:
        browser = launch_browser(p, headless=False)

        context = browser.new_context()

        page = context.new_page()

        page.goto("https://www.bilibili.com/")

        print("请在浏览器中手动登录 Bilibili")

        while True:
            input("登录完成后按回车...")

            # 判断登陆是否有效
            state = context.storage_state()

            if not check_login_online(state):
                print("未检测到有效登录，请确认已经登录成功后再按回车")
                continue

            context.storage_state(path=STATE_FILE)
            print("登录状态已经保存")
            break

        browser.close()


# =========================
# 5. 统一入口
# =========================
def ensure_login():
    """有可用 cookie 就跳过登录，否则弹出浏览器手动登录；返回最终 state。"""
    state = load_state()

    if not has_cookie(state):
        login()
        return load_state()

    if check_login_online(state):
        print("检测到有效登录状态，跳过登录")
        return state

    print("cookie 已失效，重新登录")
    login()
    return load_state()


# 统一命令行入口：bilibili -l
if __name__ == "__main__":
    # load_state()
    ensure_login()
    # login()
    # check_login_online()
    # has_cookie()
    get_cookie_header(load_state())

    # with sync_playwright() as p:
    #     browser = launch_browser(p)
    #     browser.close()
