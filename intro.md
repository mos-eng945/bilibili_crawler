# Bilibili 采集项目说明

本项目使用 Python、Bilibili Web 接口、Playwright 和 PySide6，采集视频公开
信息、一级评论、软字幕、弹幕、搜索结果及 UP 主公开视频，并把数据保存为
JSON 或 CSV。项目同时提供命令行和 Qt 图形界面。

本项目调用的是 Bilibili Web 端接口，不是官方开放平台 API。接口地址、字段、
访问限制和风控策略都可能随网站更新而变化。

`bilibili_state.json` 包含登录 Cookie，属于敏感文件，不应提交到 Git 仓库、
上传或分享给他人。

## 目录

- [项目定位](#项目定位)
- [功能范围](#功能范围)
- [接口总览](#接口总览)
- [环境与安装](#环境与安装)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [执行流程](#执行流程)
- [登录状态](#登录状态)
- [公共接口层](#公共接口层)
- [视频信息](#视频信息)
- [评论采集](#评论采集)
- [视频搜索](#视频搜索)
- [字幕采集](#字幕采集)
- [弹幕采集](#弹幕采集)
- [输出文件](#输出文件)
- [错误处理与重试](#错误处理与重试)
- [已知限制](#已知限制)
- [合规说明](#合规说明)

## 项目定位

项目适合以下场景：

- 学习和调试验证 Bilibili Web 接口、WBI 签名、Cookie 和 Playwright。
- 保存指定视频的公开信息、一级评论(没办法啊子评论工作量太大了)、软字幕和弹幕。
- 按关键词或热搜词搜索。
- 按 UP 主 MID 采集其全部公开视频，并补充互动数据。
- 使用图形界面配置任务、查看运行日志和预览输出数据。
- 为内容分析、选题研究或个人数据存档提供基础数据。

项目不负责以下内容：

- 不下载视频或音频文件。
- 不采集付费、充电专属、地区限制或无权访问的内容。
- 不提供持续监控或定时任务；重复运行时评论采集会重新完整采集。
- 不保证采集结果完整，所有数据都是请求时的快照。

## 功能范围

| 功能 | 数据来源 | 主要输出 |
| --- | --- | --- |
| 视频信息 | [`/x/web-interface/view`](https://api.bilibili.com/x/web-interface/view?bvid=BV1GJ411x7h7) | `video_info.json` |
| 一级评论 | [`/x/v2/reply/wbi/main`](https://api.bilibili.com/x/v2/reply/wbi/main?oid=80433022&type=1&mode=2&next=0&ps=30) | `comments_{BV号}.csv` |
| 视频搜索 | [`/x/web-interface/wbi/search/type`](https://api.bilibili.com/x/web-interface/wbi/search/type?search_type=video&keyword=被骗的小曲&page=1&page_size=20) | `search_{时间}_{数据量}.csv` |
| 热搜搜索 | [`/x/web-interface/search/square`](https://api.bilibili.com/x/web-interface/search/square?limit=10) | `hot_list.csv` 和搜索 CSV |
| UP 主公开视频 | [`/x/space/wbi/arc/search`](https://api.bilibili.com/x/space/wbi/arc/search?mid=486906719&pn=1&ps=30&order=pubdate) | `videos_{时间}_{数据量}.csv` |
| 软字幕 | [`/x/player/wbi/v2`](https://api.bilibili.com/x/player/wbi/v2?bvid=BV1GJ411x7h7&cid=137649199) | JSON、SRT |
| 弹幕 | [播放器 `/seg.so` 请求](https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid=137649199&segment_index=1) | `danmaku_{BV号}*.csv` |

## 接口总览

以下列出项目当前实际使用的接口。示例统一使用：

```text
bvid = BV1GJ411x7h7
aid  = 80433022
cid  = 137649199
mid  = 486906719
```

### 固定 API

所有接口都基于：

```text
https://api.bilibili.com
```

| 用途 | 接口 | 关键参数 | WBI | 调用位置 |
| --- | --- | --- | --- | --- |
| 获取登录状态和 WBI 密钥 | [`/x/web-interface/nav`](https://api.bilibili.com/x/web-interface/nav) | 无 | 否 | `get_wbi_mixin_key()`、`check_login_online()` |
| 获取视频详情和分 P | [`/x/web-interface/view`](https://api.bilibili.com/x/web-interface/view?bvid=BV1GJ411x7h7) | `bvid` | 否 | `get_video_info()`、`get_video_pages()` |
| 获取 UP 主粉丝数 | [`/x/relation/stat`](https://api.bilibili.com/x/relation/stat?vmid=486906719) | `vmid` | 否 | `get_up_follower_count()` |
| 获取热搜列表 | [`/x/web-interface/search/square`](https://api.bilibili.com/x/web-interface/search/square?limit=10) | `limit` | 否 | `get_hot_search()` |
| 搜索视频 | [`/x/web-interface/wbi/search/type`](https://api.bilibili.com/x/web-interface/wbi/search/type?search_type=video&keyword=被骗的小曲&page=1&page_size=20) | `search_type`、`keyword`、`page`、`page_size` | 是 | `search_videos()` |
| 获取 UP 主公开视频 | [`/x/space/wbi/arc/search`](https://api.bilibili.com/x/space/wbi/arc/search?mid=486906719&pn=1&ps=30&order=pubdate) | `mid`、`pn`、`ps`、`order` | 是 | `get_user_videos()` |
| 获取分 P 字幕轨道 | [`/x/player/wbi/v2`](https://api.bilibili.com/x/player/wbi/v2?bvid=BV1GJ411x7h7&cid=137649199) | `bvid`、`cid` | 是 | `get_player_subtitles()` |
| 获取一级评论 | [`/x/v2/reply/wbi/main`](https://api.bilibili.com/x/v2/reply/wbi/main?oid=80433022&type=1&mode=2&next=0&ps=30) | `oid`、`type`、`mode`、`next`、`pagination_str`、`ps` | 是 | `request_comment_page()` |
| 获取弹幕分段 | [`/x/v2/dm/web/seg.so`](https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid=137649199&segment_index=1) | `oid`、`type`、`segment_index` | 否 | `crawler_dm.py` 监听播放器响应 |

需要 WBI 的接口会在运行时加入：

```text
wts=当前 Unix 时间戳
w_rid=基于排序参数和 mixin_key 计算的 MD5
```

因此表中的 WBI 接口链接用于查看接口地址和参数结构，直接点击通常会返回缺少
签名或参数的错误。程序会在调用时动态生成完整查询字符串。

### 页面入口

| 用途 | 页面 | 调用位置 |
| --- | --- | --- |
| 人工登录 | [`https://www.bilibili.com/`](https://www.bilibili.com/) | `login.py` |
| 打开视频并触发弹幕请求 | [`https://www.bilibili.com/video/BV1GJ411x7h7?p=1`](https://www.bilibili.com/video/BV1GJ411x7h7?p=1) | `crawler_dm.py` |

### 动态字幕地址

`/x/player/wbi/v2` 返回的每个字幕轨道包含 `subtitle_url`。项目会直接请求该
地址下载字幕 JSON。它通常位于 `aisubtitle.hdslb.com`，并带有会过期的
`auth_key`，因此不能写成一个长期有效的固定接口。

例如，`BV1GJ411x7h7` 的简体中文字幕轨道曾返回：

```text
//aisubtitle.hdslb.com/bfs/subtitle/662b660a420431045b483f9b560057c262539b87.json?auth_key=...
```

`auth_key` 过期后该地址会失效，必须重新调用 `/x/player/wbi/v2` 获取。

### 文档中用于对照但未使用的接口

[`/x/v2/subtitle/web/view`](https://api.bilibili.com/x/v2/subtitle/web/view?oid=137649199&pid=80433022)
和 [`/x/player/v2`](https://api.bilibili.com/x/player/v2?bvid=BV1GJ411x7h7&cid=137649199)
只用于说明字幕接口差异，当前代码不会调用。

## 环境与安装

### 环境要求

- Python 3.14 或更高版本。
- Google Chrome、Microsoft Edge 或 Playwright Chromium，供弹幕采集和
  人工登录使用。
- 可访问 Bilibili 的网络环境。
- 一个可正常登录的 Bilibili 账号。

`zoneinfo` 用于把秒级时间戳转换成 `Asia/Shanghai` 时区时间。

程序启动浏览器时按 Google Chrome、Microsoft Edge、Playwright Chromium
的顺序尝试。没有 Chrome 或 Edge 时，可以安装自带 Chromium：

```powershell
python -m playwright install chromium
```

### 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

依赖统一声明在 `pyproject.toml`。命令行功能安装基础依赖即可；图形界面
还需要安装 PySide6：

```powershell
pip install -e ".[gui]"
```

需要重新编译 `dm.proto` 时，再安装开发依赖：

```powershell
pip install -e ".[dev]"
```

## 快速开始

### 图形界面

安装图形界面依赖后，可以使用统一命令启动：

```powershell
bilibili-gui
```

也可以直接运行兼容入口：

```powershell
python qt_app.py
```

图形界面包含五个工作区：

| 工作区 | 作用 |
| --- | --- |
| 视频采集 | 采集视频概览、评论、字幕或弹幕，也可以执行全部采集 |
| 关键词搜索 | 按关键词和页码范围搜索视频 |
| UP 主视频 | 按 UP 主 MID 采集全部公开视频 |
| 热搜搜索 | 获取热搜词并逐个执行视频搜索 |
| 运行日志 | 查看任务输出、清空日志或停止当前任务 |

界面会实时显示运行状态、登录状态和数据文件数量。每个任务面板都提供参数
摘要、可选命令行预览、结果目录入口和数据查看入口。任务执行期间一次只能
运行一个采集任务；任务完成后可以直接查看 CSV/JSON 数据。登录失效时，
界面会提示前往可用浏览器完成登录。
预览包含 `bvid` 的数据时，可以选中结果后点击“打开视频”，或双击“视频
编号”或“标题”单元格直接跳转到 Bilibili 视频页面。
数据预览最多加载前 `5000` 行，避免大评论或弹幕文件占用过多内存；完整
数据仍保存在原始 CSV/JSON 文件中。封面地址列支持单击打开封面，并在鼠标
悬停时显示链接颜色和下划线反馈。GUI 会保存上次输入的关键词、范围、并发
数和工作区，重新启动后自动恢复对应的数据面板。

### 命令行

安装后所有命令都以 `bilibili` 开头。每次必须选择一个操作：

| 短参数 | 长参数 | 作用 |
| --- | --- | --- |
| `-l` | `--login` | 确认登录状态，失效时重新登录 |
| `-i` | `--info` | 采集视频信息和 UP 主粉丝数 |
| `-c` | `--comments` | 采集一级评论 |
| `-s` | `--subtitles` | 采集软字幕 |
| `-d` | `--danmaku` | 采集弹幕 |
| `-a` | `--all` | 依次采集信息、字幕、弹幕和评论 |
| `-k` | `--keyword` | 按关键词搜索视频 |
| `-m` | `--mid` | 采集指定 UP 主的全部公开视频 |
| `-H` | `--hot-search` | 遍历热搜词搜索视频 |

通用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `-p` | 无 | 字幕或弹幕分 P 范围 |
| `--search-page` | 无 | 关键词搜索页范围，单值 `10` 表示 `1-10` |
| `--page-size` | `20` / `30` | 关键词和热搜搜索默认 `20`，UP 主视频默认 `30`；最大 `50` |
| `-w` | `2` | 关键词搜索、UP 主视频或热搜关键词内部并发数，限制在 `1` 到 `10` |
| `--limit` | `10` | 参与搜索的热搜词数量，最大 `50` |
| `--language` | 无 | 字幕语言，例如 `zh-CN` 或 `ai-zh` |
| `--comment-mode` | `time` | 评论排序，`time` 按时间，`hot` 按热门 |
| `--comment-page-size` | `30` | 评论每页数量，范围 `1-30` |

首次运行或登录失效时，任意需要登录的命令都会打开可用浏览器，等待人工
登录，并保存新的 `bilibili_state.json`。

本文示例视频统一使用 `BV1GJ411x7h7`（Rick Astley 官方 MV）。该视频的
`aid` 是 `80433022`，第一个分 P 的 `cid` 是 `137649199`，UP 主 `mid`
是 `486906719`。

常用命令：

```powershell
# 确认登录状态
bilibili -l

# 单独采集视频信息
bilibili -i BV1GJ411x7h7

# 单独采集一级评论
bilibili -c BV1GJ411x7h7

# 按热门排序采集评论，每页 20 条
bilibili -c BV1GJ411x7h7 --comment-mode hot --comment-page-size 20

# 采集 P1-P3 的指定语言文字稿
bilibili -s BV1GJ411x7h7 -p 1,3 --language ai-zh

# 采集 P1-P3 的弹幕
bilibili -d BV1GJ411x7h7 -p 1,3

# 依次执行视频信息、字幕、弹幕和评论
bilibili -a BV1GJ411x7h7

# 搜索关键词
bilibili -k "Python 教程"

# 采集搜索结果的第 2-4 页
bilibili -k "Python 教程" --search-page 2,4

# 采集 UP 主全部公开视频
bilibili -m 267068018 --page-size 30 -w 3

# 搜索热度最高的 20 个热搜词
bilibili -H --limit 20
```

如果执行：

```powershell
bilibili -k "Python" --search-page 2,4
```

实际采集的是第 `2`、`3`、`4` 页，不会自动补第一页。
关键词搜索使用单值时表示从第 1 页开始，例如 `--search-page 10` 等价于
`--search-page 1,10`；只采集第 10 页时使用 `--search-page 10,10`。

不填写 BV 号时使用 `config.py` 中的 `DEFAULT_BVID`。当前值为
`BV1UT42167xb`。

## 项目结构

| 文件 | 作用 |
| --- | --- |
| `config.py` | 项目根目录、默认 BVID、页码范围等公共配置和参数解析 |
| `output_paths.py` | `output/` 目录结构、路径构造函数和目录查找 |
| `session.py` | 采集会话，缓存 cookie、WBI 密钥、视频信息和输出目录 |
| `main.py` | 命令行入口，负责参数校验和功能分发 |
| `login.py` | 保存登录状态，并依次尝试 Chrome、Edge 和 Playwright Chromium |
| `bilibili_api.py` | HTTP 请求、WBI 签名、视频接口和搜索接口 |
| `crawler_info.py` | 保存视频信息和 UP 主粉丝数 |
| `crawler_comment.py` | 使用 WBI 游标采集一级评论 |
| `crawler_search.py` | 关键词视频搜索 |
| `crawler_hot.py` | 热搜批量视频搜索 |
| `crawler_up.py` | UP 主全部公开视频 |
| `crawler_common.py` | 爬虫共用的请求、并发、数据构建和文件输出 |
| `crawler_subtitle.py` | 下载软字幕并转换 SRT |
| `crawler_dm.py` | 使用 Playwright 采集弹幕 |
| `dm.proto` | 弹幕 Protobuf 结构定义 |
| `dm_pb2.py` | 根据 `dm.proto` 生成的 Python 代码 |
| `qt_app.py` | Qt 图形界面的兼容启动入口 |
| `qt_ui/app.py` | 创建 `QApplication` 并启动主窗口 |
| `qt_ui/main_window.py` | 组织 GUI 工作区，并通过 `QProcess` 调用命令行入口 |
| `qt_ui/dialogs.py` | 数据浏览、数据预览和任务完成弹窗 |
| `qt_ui/formatting.py` | 字段名称、数字和时间格式转换 |
| `qt_ui/theme.py` | Qt 全局样式 |
| `assets/` | 图形界面使用的图标和图片资源 |
| `pyproject.toml` | Python 依赖、`bilibili` 和 `bilibili-gui` 命令入口 |
| `bilibili_state.json` | Playwright 登录状态，属于敏感文件 |

## 执行流程

### 普通视频采集

1. `main.py` 解析命令行参数。
2. 调用 `ensure_login()` 检查或刷新登录状态。
3. 根据 `-i`、`-c`、`-s`、`-d` 或 `-a` 执行选中功能。
4. 各爬虫根据视频接口返回的 `owner`、`title` 和 `bvid` 生成同一个视频目录。
5. 结果写入视频目录，已有文件会被同名新文件覆盖。

`-a` 依次执行视频信息、字幕、弹幕和评论，不包含搜索、UP 主视频和热搜搜索。
评论采集最慢，放在最后执行。

### 搜索采集

关键词搜索、UP 主视频和热搜搜索是独立分支：

- 不能与 `-i`、`-c`、`-s`、`-d` 或 `-a` 同时使用。
- `-k`、`-m` 和 `-H` 不能同时使用。
- 搜索结果保存到 `output/search/`，不放入视频目录。

### 图形界面任务

1. 图形界面校验输入参数，并生成对应的 `main.py` 参数列表。
2. 使用当前 Python 解释器启动独立 `QProcess`，合并标准输出和错误输出。
3. 将命令行输出实时写入运行日志；检测到需要登录时弹窗提示。
4. 任务成功后刷新数据面板并显示保存位置，任务失败时保留退出码和日志。
5. 运行期间锁定其他启动按钮，并允许用户终止当前任务。

图形界面本身不重复实现采集逻辑，实际工作仍由同一个命令行入口执行。

## 登录状态

登录状态默认保存在：

```text
bilibili_state.json
```

该文件保存 Playwright 的 Cookie 和 localStorage。它可以直接访问已登录账号，
不应提交到公开仓库。

### 函数参考

| 函数 | 作用 | 返回值 |
| --- | --- | --- |
| `load_state()` | 读取并解析登录状态文件 | `dict / None` |
| `get_cookie_header(state=None)` | 把状态文件转换成 HTTP Cookie 请求头 | `str` |
| `has_cookie()` | 检查本地是否存在未过期的 `SESSDATA` | `bool` |
| `check_login_online()` | 请求 nav 接口验证服务端登录状态 | `bool` |
| `login()` | 打开可用浏览器，等待人工登录并保存状态 | `None` |
| `ensure_login()` | 统一检查和刷新登录状态 | `None` |

### 登录判断规则

- `expires == -1` 的 Cookie 按会话 Cookie 处理。
- `expires > 0` 时按 Unix 时间戳判断是否过期。
- `check_login_online()` 读取响应中的 `data.isLogin`。
- 网络异常导致无法验证时，当前实现会按已登录处理，后续接口请求再决定是否失败。

## 公共接口层

`bilibili_api.py` 提供通用请求、WBI 签名、视频信息、搜索和字幕接口。
项目路径、文件命名和输出文件处理不属于 API 层，分别放在 `output_paths.py`
和 `crawler_common.py`。一次运行的登录态、WBI 密钥和视频信息由
`session.py` 的 `Session` / `VideoSession` 持有，各采集任务共用同一个会话，
避免重复读盘和重复请求。

### HTTP 请求

`request_json(url, cookie)` 使用标准库 `urllib.request` 发起请求，并设置：

- `Cookie`
- `User-Agent`
- `Referer: https://www.bilibili.com/`
- 请求超时：20 秒

Bilibili JSON 接口通常返回：

```json
{
  "code": 0,
  "message": "0",
  "ttl": 1,
  "data": {}
}
```

函数只返回 `data`：

- `code == 0` 时返回业务数据。
- HTTP 错误、JSON 解析失败或 `code != 0` 时抛出 `RuntimeError`。
- `ttl` 是接口缓存相关字段，不代表登录状态有效期。

### WBI 签名

`get_wbi_mixin_key(cookie)` 请求
[`/x/web-interface/nav`](https://api.bilibili.com/x/web-interface/nav)。

从 `wbi_img.img_url` 和 `wbi_img.sub_url` 提取文件名，按
`img_key + sub_key` 拼接，再按照 `MIXIN_KEY_ENC_TAB` 重排并截取前 32 位。

`sign_wbi_params(params, mixin_key)` 的流程：

1. 加入当前 Unix 时间戳 `wts`。
2. 按参数名排序并进行 URL 编码。
3. 把规范化查询字符串与 `mixin_key` 拼接。
4. 计算 MD5，得到 `w_rid`。
5. 返回带 `wts` 和 `w_rid` 的查询字符串。

`request_wbi_json(path, params, cookie, mixin_key)` 先生成签名，再调用
`request_json()`。

### 视频接口

| 函数 | 接口 | 返回 |
| --- | --- | --- |
| `get_video_info(bvid, cookie)` | [`/x/web-interface/view`](https://api.bilibili.com/x/web-interface/view?bvid=BV1GJ411x7h7) | 完整视频信息 |
| `get_video_pages(bvid, cookie)` | [复用视频信息接口](https://api.bilibili.com/x/web-interface/view?bvid=BV1GJ411x7h7) | 分 P 列表 |
| `get_up_follower_count(mid, cookie)` | [`/x/relation/stat`](https://api.bilibili.com/x/relation/stat?vmid=486906719) | UP 主粉丝数 |

`get_video_info()` 返回标题、简介、发布时间、UP 主、分 P 和统计信息等字段。

`get_video_pages()` 返回的每个分 P 通常包含：

```json
{
  "cid": 41705210202,
  "page": 1,
  "part": "分P标题",
  "duration": 451,
  "dimension": {
    "width": 1920,
    "height": 1080,
    "rotate": 0
  }
}
```

### 搜索接口

普通关键词搜索使用
[`/x/web-interface/wbi/search/type`](https://api.bilibili.com/x/web-interface/wbi/search/type?search_type=video&keyword=Python&page=1&page_size=20)。
该接口需要动态 WBI 参数，直接点击示例链接通常只会看到缺少签名的错误。

`search_videos(keyword, cookie, mixin_key, page=1, page_size=20)` 使用关键参数：

| 参数 | 说明 |
| --- | --- |
| `search_type=video` | 只搜索视频 |
| `keyword` | 搜索关键词 |
| `page` | 页码，最小为 `1` |
| `page_size` | 每页数量，限制在 `1` 到 `50` |

返回数据的 `result` 是视频列表，`numResults` 是接口报告的结果数量。

热搜列表使用
[`/x/web-interface/search/square`](https://api.bilibili.com/x/web-interface/search/square?limit=10)。

`get_hot_search(cookie, limit=10)` 从 `trending.list` 读取热搜词。

直接在浏览器打开搜索页面时，第一页数据可能随 HTML 一起返回，因此 Network
中不一定出现 `search/type`。点击分页、排序或筛选后更容易观察到该请求。
项目不依赖浏览器抓包，而是直接调用接口，所以第一页同样可以正常采集。

### 字幕接口

`get_player_subtitles(bvid, cid, cookie, mixin_key)` 请求
[`/x/player/wbi/v2`](https://api.bilibili.com/x/player/wbi/v2?bvid=BV1GJ411x7h7&cid=137649199)。
该接口需要动态 WBI 参数。

返回当前分 P 的字幕轨道。当前实现使用每个轨道中的 `subtitle_url` 下载
字幕正文，不处理加密的 `subtitle_url_v2`。

### 输出路径函数

`output_paths.py` 集中定义 `output/` 的目录常量、路径构造函数，以及界面回查
数据用的查找函数。

| 函数 | 作用 |
| --- | --- |
| `safe_filename(value)` | 替换 Windows 文件名非法字符，并清理末尾空格和句点 |
| `get_video_dir(video_info)` | 生成 `output/bvid/{UP主}_{标题}_{BV号}/` |
| `get_search_dir(keyword)` | 生成 `output/search/{关键词}/` |
| `get_up_dir(mid, name)` | 生成 `output/up/{MID}+{名字}/` |
| `get_hot_run_dir(run_time)` | 生成 `output/hot_search/{运行时间}/` |
| `timestamped_path(...)` / `run_timestamp()` | 生成带运行时间的文件名 |

界面侧还会用到 `video_project_dir()`、`search_project_dir()`、
`find_user_dir()`、`hot_project_dir()`、`latest_search_keyword()`、
`latest_user_mid()` 等查找函数。

`get_video_dir()` 读取视频数据的 `owner.name`、`title` 和 `bvid`。缺少字段时
分别使用 `unknown`、`untitled` 和 `unknown`。

## 视频信息

`crawler_info.py` 的 `VideoInfoCrawler` 保存视频公开信息和 UP 主粉丝数。

### 采集流程

1. 请求视频详情接口。
2. 读取 `stat` 和 `owner`。
3. 请求 [`/x/relation/stat`](https://api.bilibili.com/x/relation/stat?vmid=486906719) 获取 UP 主粉丝数。
4. 生成视频目录并写入 `video_info.json`。

### 时间格式化

`format_published_at(timestamp)` 使用 `Asia/Shanghai` 时区转换秒级时间戳：

```text
2026-09-13T12:00:00+08:00
```

### 输出字段

| 字段 | 含义 |
| --- | --- |
| `title` | 视频标题 |
| `like` | 点赞数 |
| `coin` | 投币数 |
| `favorite` | 收藏数 |
| `share` | 分享数 |
| `published_at` | 发布时间，ISO 8601 格式 |
| `view` | 播放数 |
| `description` | 视频简介 |
| `up_name` | UP 主昵称 |
| `reply` | 视频总评论数，包含一级评论下面的子评论 |
| `danmaku` | 弹幕数 |
| `up_follower_count` | UP 主粉丝数 |

`VideoInfoCrawler(session).run()` 返回 `video_info.json` 的完整路径。

## 评论采集

`crawler_comment.py` 采集视频的全部一级评论，并保存为 CSV。

### 接口与分页

使用 WBI 游标分页接口
[`/x/v2/reply/wbi/main`](https://api.bilibili.com/x/v2/reply/wbi/main?oid=80433022&type=1&mode=2&next=0&ps=30)。
直接点击示例链接通常只会看到缺少签名的错误，实际请求必须动态生成 WBI 参数。

关键参数：

| 参数 | 说明 |
| --- | --- |
| `oid` | 视频 `aid`，不能直接填写 `bvid` |
| `type=1` | 评论对象类型为视频 |
| `mode` | `2` 按时间排序，`3` 按热门排序 |
| `next` | 下一页游标 |
| `pagination_str` | 下一页 offset |
| `ps=30` | 每页评论数量，默认 `30`，最大 `30` |

采集循环会结合 `is_end` 和 `next_offset` 判断是否结束，并按照 `rpid` 去重。
每次运行都会从第一页开始完整采集，去重排序后覆盖原有评论 CSV。
任务中断后再次运行，同样会重新从第一页开始完整采集。

### 评论对象类型

`type` 的其他常见取值来自接口和社区整理，实际含义应以 Bilibili 返回为准：

| `type` | 评论区类型 | `oid` 的含义 |
| --- | --- | --- |
| `1` | 视频稿件 | 视频 `aid` |
| `2` | 话题 | 话题 ID |
| `4` | 活动 | 活动 ID |
| `5` | 小视频 | 小视频 ID |
| `6` | 小黑屋封禁信息 | 封禁公示 ID |
| `7` | 公告信息 | 公告 ID |
| `8` | 直播活动 | 直播间 ID |
| `9` | 活动稿件 | 待验证 |
| `10` | 直播公告 | 待验证 |
| `11` | 相簿或图片动态 | 相簿 ID |
| `12` | 专栏 | 专栏 `cvid` |
| `13` | 票务 | 待验证 |
| `14` | 音频 | 音频 `auid` |
| `15` | 风纪委员会 | 众裁项目 ID |
| `16` | 点评 | 待验证 |
| `17` | 动态，包括纯文字动态和分享 | 动态 ID |
| `18` | 播单 | 待验证 |
| `19` | 音乐播单 | 待验证 |
| `20` | 漫画 | 待验证 |
| `21` | 漫画 | 待验证 |
| `22` | 漫画 | 漫画 `mcid` |
| `33` | 课程 | 课程 `epid` |

### 评论排序模式

| `mode` | 排序方式 | 说明 |
| --- | --- | --- |
| `0` | 默认排序 | 通常会被服务端归一到热门排序 |
| `1` | 综合排序 | 名称通常为“评论”，顺序不稳定 |
| `2` | 按时间排序 | 名称通常为“最新评论”，本项目默认使用 |
| `3` | 按热度排序 | 名称通常为“热门评论”，顺序会随点赞变化 |

### 文本和图片处理

`normalize_text(value)` 会把评论文本转成适合 CSV 的单行形式：

- 统一换行符。
- 连续空格压缩为一个空格。
- 换行保存为字面量 `\n`。

`parse_image_urls(content)` 从 `content.pictures` 读取图片地址：

- 协议相对地址 `//...` 会补成 `https://...`。
- `http://...` 会改成 `https://...`。
- 只保存 URL，不下载图片。

### `parse_comment(comment)` 输出字段

| 输出字段 | 接口来源 | 类型 | 含义 | 缺失时 |
| --- | --- | --- | --- | --- |
| `rpid` | `comment.rpid` | `int` | 评论唯一 ID，用于去重和标识评论 | `None` |
| `mid` | `comment.mid` | `int` | 发表评论的用户 ID | `None` |
| `user_name` | `comment.member.uname` | `str` | 评论者昵称，经过 `normalize_text()` 清理 | 空字符串 |
| `user_level` | `comment.member.level_info.current_level` | `int` | 评论者当前等级，通常为 `0` 到 `6` | `0` |
| `message` | `comment.content.message` | `str` | 评论正文，转换为适合 CSV 的单行文本 | 空字符串 |
| `ctime` | `comment.ctime` | `int` | 评论发布时间，秒级 Unix 时间戳 | `0` |
| `like` | `comment.like` | `int` | 评论点赞数 | `0` |
| `reply_count` | `comment.count` | `int` | 评论下的回复数量；接口字段名是 `count` | `0` |
| `state` | `comment.state` | `int` | 评论状态；`0` 通常表示正常 | `0` |
| `ip_location` | `comment.reply_control.location` | `str` | 评论 IP 属地，去掉“IP属地：”前缀 | 空字符串 |
| `image_urls` | `comment.content.pictures` | `list[str]` | 评论图片 URL 列表 | 空列表 |

`reply_count` 只是回复数量，不包含子评论正文。需要子评论正文时，必须根据
评论 `rpid` 再请求对应接口。

### 评论计数

必须区分两个数字：

- 一级评论数：CSV 实际保存的行数，也是直接回复视频的顶层评论数。
- 视频总评论数：接口 `cursor.all_count`，包含一级评论下面的子评论。

### 输出文件

```text
comments_{BV号}.csv
```

CSV 列顺序与 `parse_comment()` 的输出字段一致，其中 `image_urls` 会使用
`|` 连接多个图片地址。

`CommentCrawler(session, mode=2, page_size=30).run()` 返回 CSV 的完整路径。
采集过程中会逐页追加结果。评论使用 WBI 游标分页，必须顺序请求，因此没有
并发参数。

## 视频搜索

关键词搜索位于 `crawler_search.py` 的 `SearchCrawler`，热搜搜索位于
`crawler_hot.py` 的 `HotSearchCrawler`，UP 主视频位于 `crawler_up.py` 的
`UpVideosCrawler`，公共请求与格式化逻辑位于 `crawler_common.py`。

### 关键词搜索流程

1. 读取 Cookie 和 WBI 密钥。
2. 校验关键词、页码、页数、每页数量和线程数。
3. 并发请求指定范围的搜索页。
4. 按照 `bvid` 去重，只保留第一次出现的结果。
5. 把搜索结果转换成 CSV 行。
6. 按 UP 主 `mid` 去重后，并发请求粉丝数。
7. 按照搜索结果顺序写入 CSV。

### 发布时间

搜索结果中的 `pubdate` 是秒级时间戳。输出字段 `published_at` 会转换成
`Asia/Shanghai` 时区的 ISO 时间。

`published_at` 直接使用搜索结果中的 `pubdate`。时间缺失或无法转换时，
`published_at` 为空字符串。

### 并发与重试

`run_concurrently()` 在并发数大于 `1` 时使用 `ThreadPoolExecutor` 处理输入，
并按原顺序返回结果；并发数为 `1` 时直接顺序执行，不创建线程池。

`request_with_retry()` 捕获 `RuntimeError`，最多尝试三次：

- 第一次失败后等待 1 秒。
- 第二次失败后等待 2 秒。
- 第三次失败时重新抛出异常。

粉丝数使用安全包装函数。单个粉丝请求失败时不会中断整个搜索任务，而是
将对应作者的粉丝数回退为 `0`。

### 搜索 CSV 字段

| 列名 | 含义 |
| --- | --- |
| `bvid` | 视频 BV 号 |
| `title` | 视频标题，已移除搜索高亮标签 |
| `published_at` | 发布时间 |
| `author` | UP 主名称 |
| `mid` | UP 主用户 ID |
| `partition` | 视频分区名称 |
| `tags` | 视频标签，多个标签用逗号连接 |
| `duration_seconds` | 视频时长，单位为秒 |
| `cover_url` | 视频封面 URL |
| `like` | 点赞数 |
| `comment_count` | 评论数 |
| `favorite_count` | 收藏数 |
| `share_count` | 分享数 |
| `author_follower_count` | UP 主粉丝数 |
| `play_count` | 播放数 |
| `danmaku_count` | 弹幕数 |

普通视频搜索接口不提供视频级官方热度字段，因此搜索 CSV 不包含
`heat_score`。热搜关键词的热度只写入 `hot_list.csv`。

### UP 主全部视频

`UpVideosCrawler(session, mid, page_size=30, workers=2).run()` 通过 UP 主
`mid` 读取其公开视频列表。第一次请求取得总数后，剩余分页并发抓取，并按
`bvid` 去重。CSV 字段与关键词搜索一致，输出到：

```text
output/up/{MID}+{UP主名字}/videos_{时间}_{数据量}.csv
```

命令行使用 `bilibili -m MID`，可通过 `--page-size` 调整每页数量，最大为
`50`，通过 `-w` 调整并发数量。

### 热搜搜索

`HotSearchCrawler(session, limit=10, page=1, pages=1, page_size=20, workers=2)`：

1. 请求热搜列表。
2. 按榜单顺序串行处理热搜词。
3. 单个热搜词内部按 `workers` 并发请求搜索页和作者信息。
4. 单个热搜词失败时记录错误并继续处理后续词。
5. 写入 `hot_list.csv` 和每个关键词的搜索 CSV。

命令行 `-H` 不支持 `--search-page`，固定对每个热搜词只搜索第 1 页。CLI 可调整
`--limit`、`--page-size` 和 `-w`。

`hot_list.csv` 字段：

| 字段 | 含义 |
| --- | --- |
| `rank` | 热搜排名 |
| `keyword` | 实际搜索关键词 |
| `show_name` | 热搜展示名称 |
| `heat_score` | 热搜关键词热度 |
| `status` | `success` 或 `failed` |
| `error` | 失败原因，成功时为空 |

### 搜索输出路径

普通搜索：

```text
output/search/{关键词}/search_{时间}_{数据量}.csv
```

热搜搜索：

```text
output/hot_search/{运行时间}/{热搜词}/search_{时间}_{数据量}.csv
output/hot_search/{运行时间}/hot_list.csv
```

运行时间格式为 `YYYYMMDD_HHMMSS`。

## 字幕采集

`crawler_subtitle.py` 的 `SubtitleCrawler` 下载视频软字幕，并同时生成
JSON 和 SRT。

### 采集流程

1. 读取 Cookie 和 WBI 密钥。
2. 获取视频详情和所有分 P。
3. 对每个分 P 调用 [`/x/player/wbi/v2`](https://api.bilibili.com/x/player/wbi/v2?bvid=BV1GJ411x7h7&cid=137649199)。
4. 读取字幕轨道的 `subtitle_url` 并下载 JSON。
5. 保存原始字幕数据，并生成 SRT。

`-p START,END` 可以限制分 P 范围，`--language` 可以限制语言，例如
`zh-CN` 或 `ai-zh`。不传过滤参数时采集全部可用字幕。没有软字幕时只打印
提示，不生成文件。

### 字幕接口选择

| 接口 | 数据格式 | 轨道地址 | 当前是否使用 |
| --- | --- | --- | --- |
| [`/x/player/wbi/v2`](https://api.bilibili.com/x/player/wbi/v2?bvid=BV1GJ411x7h7&cid=137649199) | JSON | `subtitle_url` | 使用 |
| [`/x/v2/subtitle/web/view`](https://api.bilibili.com/x/v2/subtitle/web/view?oid=137649199&pid=80433022) | Protobuf | 通常只有加密的 `subtitle_url_v2` | 不使用 |
| [`/x/player/v2`](https://api.bilibili.com/x/player/v2?bvid=BV1GJ411x7h7&cid=137649199) | JSON | 可能返回缓存字幕 | 不使用 |

项目不使用
[`/x/player/v2`](https://api.bilibili.com/x/player/v2?bvid=BV1GJ411x7h7&cid=137649199)，
因为实测可能返回其他视频的字幕缓存。直接合并这些轨道会把无关内容写入
当前视频。

### 空字幕判断

当接口返回：

```json
{
  "allow_submit": false,
  "lan": "",
  "lan_doc": "",
  "subtitles": []
}
```

表示当前分 P 没有公开软字幕。`need_login_subtitle=False` 表示空结果不是
登录权限造成的。

### 硬字幕

画面中烧录的硬字幕不属于字幕接口数据。字幕接口无法直接获取，只能使用
OCR 近似识别：

1. 获取视频画面。
2. 固定帧率抽样，或只在画面变化时抽样。
3. 裁切字幕区域。
4. 使用 PaddleOCR、RapidOCR 等工具识别。
5. 合并连续相同文本。
6. 根据帧时间生成 SRT。

OCR 结果可能有错字，时间轴精度取决于抽样频率和视频中的字幕变化速度。

### 保存函数

`save_subtitle()` 为每条字幕轨道生成：

```text
subtitle_{BV号}_p{分P}_{语言}.json
subtitle_{BV号}_p{分P}_{语言}.srt
```

JSON 外层字段：

| 字段 | 含义 |
| --- | --- |
| `bvid` | 视频 BV 号 |
| `cid` | 当前分 P 的 CID |
| `page` | 分 P 序号 |
| `part` | 分 P 标题 |
| `language` | 字幕语言代码 |
| `language_name` | 字幕语言名称 |
| `subtitle` | 原始字幕 JSON，正文位于 `subtitle.body` |

`subtitle_to_srt(subtitle)` 读取 `body` 并生成 SRT。
`format_srt_timestamp(seconds)` 输出 `HH:MM:SS,mmm` 格式的时间。

重新采集不会自动删除旧字幕文件。如果视频字幕发生变化，旧文件需要人工清理。

## 弹幕采集

`crawler_dm.py` 的 `DanmakuCrawler` 使用 Playwright 打开视频页面，监听播放器
发出的弹幕请求。

### 数据来源

播放器请求
[`/x/v2/dm/web/seg.so`](https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid=137649199&segment_index=1)。
该接口通常还依赖浏览器请求头和登录状态。

响应是 Protobuf，由 `dm_pb2.DmSegMobileReply` 解码。每个弹幕元素由
`DanmakuElem` 描述。

### `DanmakuElem` 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `int64` | 弹幕 ID |
| `progress` | `int64` | 弹幕出现时间，单位毫秒 |
| `mode` | `int32` | 显示模式，例如滚动、顶部、底部 |
| `fontsize` | `int32` | 字号 |
| `color` | `uint32` | 十进制 RGB 颜色 |
| `midHash` | `string` | 发送用户的匿名 Hash |
| `content` | `string` | 弹幕文字 |
| `ctime` | `int64` | 发送时间，Unix 时间戳 |
| `weight` | `int32` | 显示或排序权重 |
| `action` | `string` | 附加行为，通常为空 |
| `pool` | `int32` | 弹幕池编号 |
| `idStr` | `string` | 弹幕 ID 的字符串形式 |

### 采集流程

1. 使用登录状态打开可用浏览器。
2. 监听 `/seg.so` 响应。
3. 校验响应中的 `oid` 是否等于当前分 P 的 `cid`。
4. 解码 Protobuf。
5. 按弹幕 ID、时间点和内容去重。
6. 追加写入 CSV。

播放器通常一次加载约 120 秒的弹幕。程序每 120 秒跳转一次播放位置，触发
不同时间段的请求。采集结果可能受播放器策略、网络状态和视频长度影响。

### 弹幕 CSV 字段

| 列名 | 含义 |
| --- | --- |
| `时间(ms)` | 弹幕出现时间 |
| `内容` | 弹幕文字 |
| `颜色` | 十进制 RGB 颜色 |
| `模式` | 弹幕显示模式 |
| `用户Hash` | 发送用户的匿名 Hash |

`bilibili -d` 运行时可以传入 BV 号和 `-p START,END`。

## 输出文件

`output/` 下按类别分为四个平级目录：

```text
output/
├── bvid/          视频数据
├── search/        关键词搜索
├── up/            UP 主视频
└── hot_search/    热搜搜索
```

### 视频目录

```text
output/bvid/
└── {UP主}_{标题}_{BV号}/
    ├── video_info.json
    ├── comments_{BV号}.csv
    ├── subtitle_{BV号}_p1_{语言}.json
    ├── subtitle_{BV号}_p1_{语言}.srt
    ├── danmaku_{BV号}.csv
    └── danmaku_{BV号}_p1.csv
```

单 P 视频的弹幕文件为 `danmaku_{BV号}.csv`。多 P 视频会为每个分 P 生成带
`_p{分P}` 后缀的文件。

标题中的 `?`、`:`、`/`、`\`、`|`、`*` 等非法文件名字符会替换为 `_`。

### 搜索目录

```text
output/search/
└── {关键词}/
    └── search_{时间}_{数据量}.csv

output/up/
└── {MID}+{UP主名字}/
    └── videos_{时间}_{数据量}.csv

output/hot_search/
└── {运行时间}/
    ├── hot_list.csv
    └── {热搜词}/
        └── search_{时间}_{数据量}.csv
```

搜索数据不会写入视频目录。

## 错误处理与重试

| 模块 | 行为 |
| --- | --- |
| `login.py` | 服务端确认 Cookie 失效时重新登录；网络异常时先按已登录处理 |
| `crawler_comment.py` | 评论页请求最多重试三次，每次间隔一秒 |
| `crawler_common.py` | 搜索请求最多重试三次，等待时间依次为 1 秒和 2 秒 |
| `crawler_common.py` | 搜索结果直接生成数据行，粉丝数失败回退为 `0` |
| `crawler_subtitle.py` | 单条字幕缺少 `subtitle_url` 时跳过 |
| `crawler_dm.py` | 只处理状态正常的 `/seg.so` 响应 |

当前没有统一的全局限速器。批量搜索或大视频评论采集时，应主动降低并发数。

## 已知限制

- Bilibili Web 接口不是稳定公共 API，字段和限制可能随时变化。
- 充电专属、付费、地区限制或仅自己可见的视频可能无法访问。
- 视频信息是请求时的快照，不会自动更新。
- 评论只包含一级评论，不包含完整子评论正文。
- 评论图片只保存 URL，CDN 地址可能失效。
- 弹幕采用分段跳转采集，可能存在延迟、重复或遗漏。
- 当前软字幕接口可能返回空列表。
- [`/x/player/v2`](https://api.bilibili.com/x/player/v2?bvid=BV1GJ411x7h7&cid=137649199) 可能返回错误缓存字幕，因此项目不使用该接口。
- 音乐视频的 AI 字幕经常只输出“音乐”，不能当作完整歌词。
- 硬字幕不支持直接采集，只能通过 OCR 近似识别。
- 搜索接口不提供视频级官方热度，普通搜索 CSV 不包含 `heat_score`。
- 热搜关键词的 `heat_score` 保存在 `hot_list.csv`，与视频热度不是同一指标。
- 搜索接口不提供分享数，关键词搜索的 `share_count` 固定为 `0`。
- 旧字幕文件不会因为接口返回变化而自动删除。
- 输出文件使用同名覆盖策略，不会自动创建历史版本。

## 合规说明

请合理设置请求频率，仅采集你有权访问和使用的内容，并遵守 Bilibili 用户
协议、网站规则和相关法律法规。评论和其他用户数据可能涉及个人信息，公开
或二次使用前应确认授权和适用范围。
