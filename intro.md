# Bilibili 采集项目说明

本项目通过 Bilibili Web 接口和 Playwright 浏览器自动化，采集视频公开信息、
一级评论、软字幕和弹幕。它不是 Bilibili 官方开放平台 API，接口字段和访问
策略可能随网站更新而变化。

## 整体流程

`main.py` 是统一入口。功能通过命令行开关选择，不再默认全部执行：

1. 调用 `ensure_login()` 检查登录状态。
2. 根据功能开关调用对应采集器。

| 功能开关 | 调用的函数 | 额外参数 |
| --- | --- | --- |
| `--info` | `crawl_video_info()` | 无 |
| `--comments` | `crawl_comments()` | 无 |
| `--subtitles` | `crawl_subtitles()` | `--subtitle-page`、`--subtitle-language` |
| `--danmaku` | `goto()` | `--danmaku-page` |
| `--all` | 依次调用全部功能 | 可使用各功能自己的额外参数 |

运行方式：

```powershell
python main.py BV号 --info
python main.py BV号 --comments
python main.py BV号 --subtitles
python main.py BV号 --danmaku
python main.py BV号 --all
```

不传 BV 号时使用 `main.py` 中的 `DEFAULT_BVID`。不选择任何功能时，
程序会提示必须先选择 `--info`、`--comments`、`--subtitles`、
`--danmaku` 或 `--all`。

## 命令行参数

| 入口 | 参数 | 必填 | 说明 |
| --- | --- | --- | --- |
| `main.py` | `bvid` | 否 | 位置参数；省略时使用 `DEFAULT_BVID` |
| `main.py` | `--info` | 否 | 只采集视频信息 |
| `main.py` | `--comments` | 否 | 只采集一级评论 |
| `main.py` | `--subtitles` | 否 | 只采集字幕 |
| `main.py` | `--subtitle-page` | 否 | 只采集指定字幕分 P |
| `main.py` | `--subtitle-language` | 否 | 只采集指定字幕语言 |
| `main.py` | `--danmaku` | 否 | 只采集弹幕 |
| `main.py` | `--danmaku-page` | 否 | 只采集指定弹幕分 P |
| `main.py` | `--all` | 否 | 依次执行全部功能 |
| `crawler_info.py` | 无 | - | 只使用代码中的 `DEFAULT_BVID` |
| `crawler_comment.py` | `bvid` | 否 | 位置参数；省略时使用 `DEFAULT_BVID` |
| `crawler_comment.py` | `--workers` | 否 | 兼容旧参数；WBI 游标分页要求顺序请求，当前不生效 |
| `crawler_subtitle.py` | `bvid` | 否 | 位置参数；省略时使用 `DEFAULT_BVID` |
| `crawler_subtitle.py` | `--page` | 否 | 只采集指定分 P |
| `crawler_subtitle.py` | `--language` | 否 | 只采集指定语言 |
| `crawler_dm.py` | 无 | - | 只使用代码中的 `DEFAULT_BVID` |
| `login.py` | 无 | - | 检查登录状态，必要时打开浏览器登录 |

各模块入口函数：

| 函数 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `main()`（`main.py`） | 无 | `None` | 解析命令行参数并执行选中的功能 |
| `main()`（`crawler_info.py`） | 无 | `None` | 检查登录后采集默认视频信息 |
| `main()`（`crawler_comment.py`） | 无 | `None` | 解析命令行参数并采集评论 |
| `main()`（`crawler_subtitle.py`） | 无 | `None` | 检查登录后采集默认视频字幕 |

## login.py

负责保存、检查和复用 Bilibili 登录状态。

登录状态默认保存在：

```text
bilibili_state.json
```

该文件包含 Cookie，属于敏感信息，不应提交到 Git 仓库或分享给他人。

### `load_state()`

读取 `bilibili_state.json`。文件不存在、损坏或无法解析时返回 `None`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 固定读取 `STATE_FILE` |

返回：`dict | None`，即 Playwright storage state 或空值。

### `get_cookie_header(state=None)`

把 Playwright storage state 中的 Cookie 列表转换成 HTTP 请求使用的
Cookie 字符串。

不传 `state` 时自动读取 `bilibili_state.json`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `state` | `dict / None` | 否 | Playwright storage state；省略时读取本地文件 |

返回：`str`，可直接放入 HTTP `Cookie` 请求头的字符串。

### `has_cookie()`

检查本地状态中是否存在未过期的 `SESSDATA`。

`expires == -1` 表示会话 Cookie；大于零时按 Unix 时间戳判断是否过期。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 内部读取 `bilibili_state.json` |

返回：`bool`，本地是否存在未过期的 `SESSDATA`。

### `check_login_online()`

请求：

```text
https://api.bilibili.com/x/web-interface/nav
```

通过响应中的 `data.isLogin` 判断服务端是否仍认可当前登录态。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 内部读取 Cookie 并请求 nav 接口 |

返回：`bool`，登录有效时为 `True`。

### `login()`

打开 Chrome，等待人工登录。登录完成后调用：

```python
context.storage_state(path=STATE_FILE)
```

并保存新的登录状态。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 打开 Chrome 并等待用户手动登录 |

返回：`None`。

### `ensure_login()`

统一登录入口：

1. 本地没有 `SESSDATA` 时打开浏览器登录。
2. 本地有 Cookie 但服务端已经失效时重新登录。
3. 登录有效时直接跳过。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 根据本地和在线状态决定是否登录 |

返回：`None`。

## bilibili_api.py

封装通用 HTTP 请求、WBI 签名、视频信息接口和字幕接口。

### `request_json(url, cookie)`

发起普通 JSON 请求，并检查 Bilibili 的业务错误码。

正常响应结构：

```json
{
  "code": 0,
  "message": "0",
  "ttl": 1,
  "data": {}
}
```

- `code == 0`：业务成功。
- `message`：接口消息。
- `ttl`：接口缓存相关字段，不代表登录状态有效期。
- `data`：实际业务数据。

函数只返回 `data`，业务失败时抛出 `RuntimeError`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url` | `str` | 是 | 完整请求 URL |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |

返回：`dict`，即接口响应中的 `data`。

### `MIXIN_KEY_ENC_TAB`

WBI 签名使用的字符重排表。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 无 | - | - | 模块级常量，不是函数参数 |

值类型：`list[int]`，共 64 个索引。

### `get_wbi_mixin_key(cookie)`

请求 `x/web-interface/nav`，取得：

```json
{
  "wbi_img": {
    "img_url": "https://i0.hdslb.com/bfs/wbi/xxx.png",
    "sub_url": "https://i0.hdslb.com/bfs/wbi/xxx.png"
  }
}
```

从两个 URL 中提取文件名，按 `img_key + sub_key` 拼接，再使用
`MIXIN_KEY_ENC_TAB` 重排并截取前 32 位，得到 `mixin_key`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `cookie` | `str` | 是 | 请求 nav 接口所需的登录 Cookie |

返回：`str`，32 位 WBI `mixin_key`。

### `sign_wbi_params(params, mixin_key)`

为请求参数生成 WBI 签名：

1. 加入当前 Unix 时间戳 `wts`。
2. 按参数名排序并 URL 编码。
3. 把规范化查询字符串与 `mixin_key` 拼接。
4. 计算 MD5，得到 `w_rid`。
5. 返回带 `wts` 和 `w_rid` 的查询字符串。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `params` | `dict` | 是 | 原始接口参数 |
| `mixin_key` | `str` | 是 | `get_wbi_mixin_key()` 返回的密钥 |

返回：`str`，包含 `wts` 和 `w_rid` 的查询字符串。

### `request_wbi_json(path, params, cookie, mixin_key)`

先生成 WBI 签名，再调用 `request_json()` 请求接口。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | `str` | 是 | API 路径，例如 `/x/player/wbi/v2` |
| `params` | `dict` | 是 | 接口查询参数 |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |
| `mixin_key` | `str` | 是 | WBI 签名密钥 |

返回：`dict`，即接口响应中的 `data`。

### `get_video_info(bvid, cookie)`

请求：

```text
/x/web-interface/view?bvid=BV号
```

返回视频标题、分 P、统计数据、UP 主信息和简介等数据。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |

返回：`dict`，完整视频信息。

### `get_video_pages(bvid, cookie)`

复用 `get_video_info()`，只返回 `pages` 数组。

每个分 P 通常包含：

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

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |

返回：`list[dict]`，每个元素代表一个分 P。

### `get_up_follower_count(mid, cookie)`

请求：

```text
/x/relation/stat?vmid=UP主MID
```

返回 UP 主粉丝数。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `mid` | `int / str` | 是 | UP 主用户 ID |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |

返回：`int`，UP 主粉丝数。

### `_extract_subtitle_tracks(data)`

从播放器响应中读取：

```python
subtitle.get("subtitles") or subtitle.get("list") or []
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `data` | `dict` | 是 | 播放器接口返回的 `data` |

返回：`list[dict]`，字幕轨道列表；没有字幕时为空列表。

### `get_player_subtitles(bvid, cid, cookie, mixin_key)`

当前只请求：

```text
/x/player/wbi/v2
```

请求参数只有：

```json
{
  "bvid": "BV号",
  "cid": 当前分P的CID
}
```

每个可用字幕轨道通常直接包含 `subtitle_url`，下载后即可得到字幕 JSON，
不需要额外解析 Protobuf 或解密 `subtitle_url_v2`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `cid` | `int` | 是 | 指定分 P 的 CID |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |
| `mixin_key` | `str` | 是 | WBI 签名密钥 |

返回：`list[dict]`，当前分 P 的可用字幕轨道。

## 字幕接口说明

项目测试过三个相关入口。

### `/x/player/wbi/v2`

当前实现使用的接口。

- JSON 响应。
- 返回完整播放器数据，字幕位于 `data.subtitle`。
- 每个字幕轨道直接提供 `subtitle_url`。
- 正常情况下内容正确。

### `/x/v2/subtitle/web/view`

专门返回字幕列表的新接口。

- Protobuf 二进制响应。
- 需要 `oid=cid`、`pid=aid` 等参数。
- 轨道通常只提供加密的 `subtitle_url_v2`。
- 使用播放器 XOR 密钥还原后才能下载。
- 在已测试视频中，其有效字幕内容与 `/x/player/wbi/v2` 一致。

因此该接口没有提升字幕内容质量，只会增加 Protobuf 解析和解密复杂度。

### `/x/player/v2`

不需要 WBI 签名的普通播放器接口，但当前项目不使用它。

实测发现它可能返回错误缓存：

- 对一个音乐视频返回了其他视频的 iPhone 评测字幕。
- 对一个原神视频返回了其他视频的完整文字稿。
- 有时相同请求会返回不同数量和不同内容的字幕。

如果把这些错误轨道合并进正常结果，会在字幕 JSON 和 SRT 中混入无关内容。

### 空字幕结果

以下响应表示视频没有公开的软字幕轨道：

```json
{
  "allow_submit": false,
  "lan": "",
  "lan_doc": "",
  "subtitles": []
}
```

同时检查 `need_login_subtitle`：

```text
False
```

表示空字幕不是登录权限造成的。

## 硬字幕

视频画面中可见的字幕不一定存在于字幕接口中。

在播放器中关闭弹幕后，如果底部字幕仍然存在，同时
`.bpx-player-subtitle-wrap` 没有文本节点，则该字幕是直接烧录进视频画面的
硬字幕。

硬字幕属于视频像素，字幕接口无法采集。当前项目不支持硬字幕 OCR，只能通过
以下流程生成近似字幕：

1. 获取视频画面。
2. 按固定帧率或仅在画面变化时抽样。
3. 裁切字幕区域。
4. 使用 PaddleOCR、RapidOCR 等工具识别。
5. 合并连续相同文本。
6. 根据帧时间生成 SRT。

OCR 结果可能有错字，时间轴精度也受抽样频率影响。

## crawler_info.py

负责保存视频公开信息。

### `format_published_at(timestamp)`

把秒级时间戳转换为 `Asia/Shanghai` 时区的 ISO 时间。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `timestamp` | `int / float` | 是 | Unix 秒级时间戳 |

返回：`str`，例如 `2026-09-13T12:00:00+08:00`。

### `crawl_video_info(bvid=DEFAULT_BVID)`

保存以下字段到 `video_info.json`：

- `title`
- `like`
- `coin`
- `favorite`
- `share`
- `published_at`
- `view`
- `description`
- `up_name`
- `reply`
- `danmaku`
- `up_follower_count`

其中 `reply` 是视频总评论数，包含一级评论下面的子评论。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 否 | 视频 BV 号；默认使用 `DEFAULT_BVID` |

返回：`Path`，`video_info.json` 的完整路径。

## crawler_comment.py

负责采集视频的一级评论和顶层置顶评论，并保存为 CSV。

### 评论接口

使用 WBI 游标分页接口：

```text
/x/v2/reply/wbi/main
```

关键参数包括：

- `oid`：视频 aid。
- `type=1`：视频评论。
- `mode=2`：按时间排序。
- `next`：下一页游标。
- `pagination_str`：翻页 offset。
- `ps=30`：每页数量。

### `parse_image_urls(content)`

提取评论图片地址，并统一转换成 HTTPS URL。只保存地址，不下载图片。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content` | `dict` | 是 | 评论 `content` 对象，读取其中的 `pictures` |

返回：`list[str]`，统一为 HTTPS 的图片地址列表。

### `normalize_text(value)`

把评论文本转换成适合 CSV 的单行形式：

- 统一换行符。
- 连续空格压缩为一个空格。
- 换行保存为字面量 `\n`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `value` | `Any` | 是 | 原始文本或可转换为文本的值 |

返回：`str`，适合写入单行 CSV 的文本。

### `parse_comment(comment)`

从接口评论对象中提取轻量字段。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `comment` | `dict` | 是 | 评论接口中的单条评论对象 |

返回：`dict`，包含评论 CSV 所需字段。

### `request_comment_page(oid, page_cursor, cookie, mixin_key)`

请求一页一级评论。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `oid` | `int` | 是 | 视频 aid |
| `page_cursor` | `dict` | 是 | 游标，可包含 `next` 和 `offset` |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |
| `mixin_key` | `str` | 是 | WBI 签名密钥 |

返回：`dict`，评论接口的 `data`。

### `request_comment_page_with_retry(oid, page_cursor, cookie, mixin_key)`

请求失败时最多重试三次，每次间隔一秒。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `oid` | `int` | 是 | 视频 aid |
| `page_cursor` | `dict` | 是 | 当前页游标 |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |
| `mixin_key` | `str` | 是 | WBI 签名密钥 |

返回：`dict`，重试成功后的评论接口数据。

### `extract_page_comments(data, include_top=False)`

提取当前页评论。第一页会同时包含 `top_replies` 和普通 `replies`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `data` | `dict` | 是 | 一页评论接口数据 |
| `include_top` | `bool` | 否 | 是否包含 `top_replies`，默认 `False` |

返回：`list[dict]`，本页一级评论记录。

### `crawl_comments(bvid=DEFAULT_BVID, workers=None)`

采集流程：

1. 使用 BV 号取得 aid。
2. 取得 WBI 签名密钥。
3. 按时间游标依次请求评论页。
4. 按照 `rpid` 去重。
5. 写入 `comments_{BV号}.csv`。

评论计数必须区分：

- `一级评论数`：CSV 实际保存的行数，也是直接回复视频的顶层评论数。
- `视频总评论数`：接口 `cursor.all_count`，包含一级评论下面的子评论。

运行日志会分别显示两个数字。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 否 | 视频 BV 号；默认使用 `DEFAULT_BVID` |
| `workers` | `int / None` | 否 | 兼容旧调用；传入后只提示不生效 |

返回：`Path`，`comments_{BV号}.csv` 的完整路径。

### 评论 CSV 列

| 列名 | 含义 |
| --- | --- |
| `rpid` | 评论 ID |
| `mid` | 评论者用户 ID |
| `user_name` | 评论者昵称 |
| `user_level` | 评论者 B 站等级 |
| `message` | 评论正文 |
| `ctime` | 评论发布时间，秒级时间戳 |
| `like` | 评论点赞数 |
| `reply_count` | 该一级评论下面的子评论数量 |
| `state` | 评论状态，`0` 表示正常 |
| `image_urls` | 评论图片 URL，多个地址用 `|` 分隔 |

## crawler_subtitle.py

负责下载软字幕，并生成 JSON 和 SRT。

### `download_subtitle_json(url, cookie)`

请求 `subtitle_url`，返回字幕正文 JSON。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url` | `str` | 是 | 字幕轨道中的 `subtitle_url` |
| `cookie` | `str` | 是 | HTTP Cookie 请求头 |

返回：`dict`，字幕正文 JSON。

### `format_srt_timestamp(seconds)`

把秒数转换为 SRT 时间格式：

```text
HH:MM:SS,mmm
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `seconds` | `int / float` | 是 | 相对视频开始的秒数 |

返回：`str`，SRT 时间字符串。

### `subtitle_to_srt(subtitle)`

读取字幕 JSON 的 `body`，逐条生成 SRT 块。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subtitle` | `dict` | 是 | 字幕正文 JSON，正文位于 `body` |

返回：`str`，完整 SRT 文本。

### `save_subtitle(video_dir, bvid, cid, page_number, part, subtitle_item, subtitle_data)`

每条字幕轨道生成两个文件：

```text
subtitle_{BV号}_p{分P}_{语言}.json
subtitle_{BV号}_p{分P}_{语言}.srt
```

JSON 外层保存视频、分 P、语言和原始字幕数据。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `video_dir` | `Path` | 是 | 视频输出目录 |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `cid` | `int` | 是 | 当前分 P 的 CID |
| `page_number` | `int` | 是 | 分 P 序号 |
| `part` | `str` | 是 | 分 P 标题 |
| `subtitle_item` | `dict` | 是 | 字幕轨道元数据，如 `lan`、`lan_doc` |
| `subtitle_data` | `dict` | 是 | 下载得到的字幕正文 JSON |

返回：`tuple[Path, Path]`，依次为 JSON 路径和 SRT 路径。

### `crawl_subtitles(bvid=DEFAULT_BVID, page_number=None, language=None)`

当前流程：

1. 获取登录 Cookie 和 WBI 密钥。
2. 获取视频所有分 P。
3. 对每个分 P 调用 `get_player_subtitles()`。
4. 下载每条字幕的 `subtitle_url`。
5. 保存 JSON 并同时生成 SRT。

没有软字幕时只打印提示，不生成新文件。

如果视频此前留下过错误字幕文件，重新采集不会自动删除旧文件，需要人工确认
和清理。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 否 | 视频 BV 号；默认使用 `DEFAULT_BVID` |
| `page_number` | `int / None` | 否 | 只处理指定分 P；省略时处理全部 |
| `language` | `str / None` | 否 | 只处理指定语言，例如 `zh-CN`、`ai-zh` |

返回：`None`。

## crawler_dm.py

使用 Playwright 监听播放器请求，采集弹幕。

### 弹幕请求

播放器请求：

```text
/x/v2/dm/web/seg.so
```

响应是 Protobuf，由 `dm_pb2.DmSegMobileReply` 解码。

### `crawl_page(page, bvid, page_info, total_pages, video_dir, use_page_suffix)`

采集一个分 P：

1. 监听 `/seg.so` 响应。
2. 校验响应中的 `oid` 是否等于当前分 P 的 `cid`。
3. 使用 Protobuf 解码弹幕。
4. 按弹幕 ID、时间点和内容去重。
5. 追加写入 CSV。

播放器通常一次加载约 120 秒的弹幕，因此代码每 120 秒跳转一次播放位置，
触发不同时间段的请求。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `playwright.sync_api.Page` | 是 | 已打开的浏览器页面 |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `page_info` | `dict` | 是 | 当前分 P 信息，需包含 `cid` 和可选 `page`、`part` |
| `total_pages` | `int` | 是 | 视频总 P 数，用于日志显示 |
| `video_dir` | `Path` | 是 | 视频输出目录 |
| `use_page_suffix` | `bool` | 是 | 是否在弹幕文件名中加入分 P 后缀 |

返回：`int`，当前分 P 写入的弹幕数量。

### `goto(bvid, page_number=None)`

打开 Chrome，加载 `bilibili_state.json`，遍历全部分 P 并汇总弹幕数量。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bvid` | `str` | 是 | 视频 BV 号 |
| `page_number` | `int / None` | 否 | 只采集指定分 P；省略时采集全部 |

返回：`None`。

### 弹幕 CSV 列

| 列名 | 含义 |
| --- | --- |
| `时间(ms)` | 弹幕出现时间 |
| `内容` | 弹幕文字 |
| `颜色` | 十进制 RGB 颜色 |
| `模式` | 弹幕显示模式 |
| `用户Hash` | 发送用户的匿名 Hash |

## video_paths.py

统一管理输出目录和文件名。

### `safe_filename(value)`

替换 Windows 文件名不允许的字符：

```text
< > : " / \ | ? *
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `value` | `Any` | 是 | 原始文件名或路径片段 |

返回：`str`，替换非法字符并清理首尾空格、句点后的文件名。

### `get_video_dir(video_info)`

生成输出目录：

```text
output/{UP主}_{标题}_{BV号}/
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `video_info` | `dict` | 是 | 视频接口数据，读取 `owner.name`、`title`、`bvid` |

返回：`Path`，视频输出目录。

## 输出文件汇总

每个视频目录通常包含：

```text
video_info.json
comments_{BV号}.csv
subtitle_{BV号}_p1_{语言}.json
subtitle_{BV号}_p1_{语言}.srt
danmaku_{BV号}.csv
```

多 P 视频的弹幕文件会带上分 P 后缀。

## 已知限制

- Bilibili Web 接口不是稳定公共 API。
- `/x/player/v2` 可能返回错误的缓存字幕，因此当前项目不使用。
- 接口返回 `subtitles: []` 表示没有公开软字幕。
- 画面中的硬字幕无法通过字幕接口采集，只能使用 OCR。
- 音乐视频的 AI 字幕经常只输出“音乐”，不能当作完整歌词。
- 评论 CSV 只包含一级评论，不包含子评论正文。
- 视频信息、评论和弹幕都是采集时的快照。
- 旧字幕文件不会在视频字幕消失后自动清理。
