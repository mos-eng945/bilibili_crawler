# Bilibili 视频信息、评论、字幕与弹幕采集器

这是一个基于 Python 和 Playwright 的 Bilibili 数据采集工具，用于保存
视频公开信息、一级评论和字幕，并通过浏览器播放器采集弹幕。

> 本项目调用的是 Bilibili Web 端接口，并非官方开放平台 API。
> 接口、字段和访问限制可能随网站更新而变化。

## 功能

- 保存视频标题、互动数据、发布时间、简介和 UP 主信息。
- 获取 UP 主粉丝数。
- 按时间顺序并发采集视频的全部一级评论。
- 按 `rpid` 去重评论，并保存评论图片 URL。
- 下载视频中的普通字幕和 AI 字幕。
- 将字幕同时保存为 JSON 和 SRT 格式。
- 通过 Playwright 监听播放器请求并采集弹幕。
- 使用 Protobuf 解码弹幕，去重后保存为 CSV。
- 自动处理单 P 和多 P 视频。
- 复用 Playwright 登录状态，减少重复登录。

## 项目结构

| 文件 | 作用 |
| --- | --- |
| `main.py` | 主入口，依次采集视频信息、评论、字幕和弹幕 |
| `login.py` | 保存、检查和刷新 Bilibili 登录状态 |
| `bilibili_api.py` | 公共接口请求、WBI 签名和字幕接口 |
| `crawler_info.py` | 获取并保存视频信息和 UP 主粉丝数 |
| `crawler_comment.py` | 分页采集全部一级评论并保存 CSV |
| `crawler_subtitle.py` | 下载字幕 JSON 并转换 SRT |
| `crawler_dm.py` | 使用 Playwright 采集弹幕 |
| `video_paths.py` | 生成统一的视频输出目录 |
| `dm.proto` | 弹幕 Protobuf 结构定义 |
| `dm_pb2.py` | 根据 `dm.proto` 生成的 Python 代码 |

## 环境要求

- Python 3.9 或更高版本
- Google Chrome
- 可访问 Bilibili 的网络环境
- 一个可正常登录的 Bilibili 账号(得到cookie)

`zoneinfo` 用于把时间戳转换为中国时区时间，因此需要 Python 3.9 以上。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` 包含：

```text
playwright
protobuf>=6.31.1,<7
grpcio-tools
```

`grpcio-tools` 只在重新编译 `dm.proto` 时需要使用。

## 运行

主入口不再默认运行全部功能，必须至少选择一个功能。

只采集视频信息：

```powershell
python main.py BV1V3Yn6wENr --info
```

只采集一级评论：

```powershell
python main.py BV1V3Yn6wENr --comments
```

只采集字幕：

```powershell
python main.py BV1V3Yn6wENr --subtitles
```

只采集字幕的指定分 P 和语言：

```powershell
python main.py BV1V3Yn6wENr --subtitles --subtitle-page 1 --subtitle-language ai-zh
```

只采集弹幕：

```powershell
python main.py BV1V3Yn6wENr --danmaku
```

只采集指定分 P 的弹幕：

```powershell
python main.py BV1V3Yn6wENr --danmaku --danmaku-page 1
```

依次运行全部功能：

```powershell
python main.py BV1V3Yn6wENr --all
```

不填写 BV 号时，使用 `main.py` 中的 `DEFAULT_BVID`：

```powershell
python main.py --info
```

只采集一级评论：

```powershell
python crawler_comment.py BV1V3Yn6wENr
```

评论使用 WBI 游标分页顺序采集，不受旧评论接口的
`max offset exceeded` 页码上限影响。

首次运行或登录状态失效时，程序会打开 Chrome，要求手动登录。
登录完成后，Cookie 和 localStorage 会保存到 `bilibili_state.json`。

`--all` 会依次执行：

1. 检查或刷新登录状态。
2. 保存视频信息和 UP 主粉丝数。
3. 按时间顺序下载该视频的全部一级评论。
4. 下载该视频所有分 P 的字幕。
5. 打开播放器并采集所有分 P 的弹幕。

评论、字幕和弹幕可能受以下条件影响：

- 评论数量较多时需要多次分页请求，采集时间会相应增加。
- 视频没有字幕时不会生成字幕文件。
- 部分高清晰度或字幕接口需要有效登录状态。
- 弹幕采集依赖播放器实际发出的请求，可能受网络和播放器策略影响。

## 输出目录

所有结果保存在：

```text
output/{UP主}_{标题}_{BV号}/
```

标题中的 `?`、`:`、`/`、`\` 等非法文件名字符会替换为 `_`。

典型目录内容：

```text
output/
└── UP主_视频标题_BV号/
    ├── video_info.json
    ├── comments_BV号.csv
    ├── subtitle_BV号_p1_ai-zh.json
    ├── subtitle_BV号_p1_ai-zh.srt
    └── danmaku_BV号.csv
```

多 P 视频的弹幕文件会带上分 P 后缀：

```text
danmaku_{BV号}_p1.csv
danmaku_{BV号}_p2.csv
```

## 视频信息

`video_info.json` 包含以下字段：

```json
{
  "title": "视频标题",
  "like": 2091,
  "coin": 236,
  "favorite": 117,
  "share": 392,
  "published_at": "2026-09-16T12:48:57+08:00",
  "view": 43621,
  "description": "视频简介",
  "up_name": "UP主昵称",
  "reply": 730,
  "danmaku": 172,
  "up_follower_count": 39512
}
```

统计数字是采集时的快照，之后不会自动更新。

## 评论文件

评论保存为：

```text
comments_{BV号}.csv
```

当前只采集直接评论视频的一级评论，不展开一级评论下面的子评论。
采集使用时间排序，通过 WBI 游标分页依次推进，并按照 `rpid` 去重。
接口返回的 `all_count` 是视频总评论数，包含一级评论下面的子评论；CSV
实际保存的行数是一级评论数。

CSV 列如下：

| 列名 | 含义 |
| --- | --- |
| `rpid` | 评论ID |
| `mid` | 评论者用户ID |
| `user_name` | 评论者昵称 |
| `user_level` | 评论者B站等级 |
| `message` | 评论正文，换行保存为字面量 `\n` |
| `ctime` | 评论发布时间，秒级时间戳 |
| `like` | 评论点赞数 |
| `reply_count` | 子评论数量 |
| `state` | 评论状态，`0` 表示正常 |
| `image_urls` | 评论图片URL，多个地址用 `|` 分隔 |

图片只保存 URL，不下载图片文件。

评论正文中的连续空格会压缩为一个空格，连续换行会转换为一个可见的
`\n` 字符。没有图片时 `image_urls` 列为空。

## 字幕文件

每个字幕轨道会生成两个文件：

- `subtitle_{BV号}_p{分P}_{语言}.json`：接口原始数据和元信息。
- `subtitle_{BV号}_p{分P}_{语言}.srt`：可直接用于播放器的字幕文件。

字幕 JSON 的外层结构包含：

| 字段 | 含义 |
| --- | --- |
| `bvid` | 视频 BV 号 |
| `cid` | 当前分 P 的 CID |
| `page` | 分 P 序号 |
| `part` | 分 P 标题 |
| `language` | 字幕语言代码 |
| `language_name` | 字幕语言名称 |
| `subtitle` | 原始字幕数据，正文位于 `subtitle.body` |

## 弹幕文件

弹幕使用 UTF-8 BOM 编码的 CSV 保存，列如下：

| 列名 | 含义 |
| --- | --- |
| `时间(ms)` | 弹幕出现时间，单位毫秒 |
| `内容` | 弹幕文字 |
| `颜色` | 十进制 RGB 颜色 |
| `模式` | 弹幕显示模式 |
| `用户Hash` | 发送用户的匿名 Hash |

弹幕接口返回 Protobuf 数据，解码对象为 `DanmakuElem`。

## DanmakuElem 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `int64` | 弹幕 ID |
| `progress` | `int64` | 弹幕出现时间，单位毫秒 |
| `mode` | `int32` | 显示模式，例如滚动、顶部、底部 |
| `fontsize` | `int32` | 字号大小 |
| `color` | `uint32` | 十进制 RGB 颜色 |
| `midHash` | `string` | 发送用户的匿名 Hash |
| `content` | `string` | 弹幕文字内容 |
| `ctime` | `int64` | 发送时间，Unix 时间戳 |
| `weight` | `int32` | 显示或排序权重 |
| `action` | `string` | 附加行为，通常为空 |
| `pool` | `int32` | 弹幕池编号 |
| `idStr` | `string` | 弹幕 ID 的字符串形式 |

## 登录状态

登录状态默认保存在：

```text
bilibili_state.json
```

该文件包含可访问账号的 Cookie，属于敏感信息，不应提交到 Git 仓库或分享给他人。

登录流程如下：

1. 检查 `SESSDATA` 是否存在且未过期。
2. 请求 `x/web-interface/nav` 验证登录状态。
3. 登录无效时打开 Chrome，等待人工登录。
4. 保存新的 Playwright storage state。

## 已知限制

- Bilibili Web 接口不是稳定的公共 API，字段和限制可能随时变化。
- 充电专属、付费、地区限制或仅自己可见的视频可能无法访问。
- 评论采集当前只包含一级评论，不包含完整子评论。
- 评论图片只保存 URL，如果 CDN 地址失效，历史图片可能无法重新访问。
- 弹幕采用分段跳转采集，可能存在延迟、重复或遗漏；代码会按弹幕 ID、
  时间点和内容去重。
- 视频信息是采集时快照，不包含持续监控功能。
- 本项目只采集公开页面能够访问的数据，不下载视频或音频文件。

## 合规说明

请合理设置请求频率，仅采集你有权访问和使用的内容，并遵守 Bilibili
用户协议、网站规则和相关法律法规。
