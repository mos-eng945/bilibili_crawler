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
- 通过 UP 主 MID 采集其全部公开视频并补充互动数据。
- 自动处理单 P 和多 P 视频。
- 复用 Playwright 登录状态，减少重复登录。

## 项目结构

| 文件 | 作用 |
| --- | --- |
| `config.py` | 项目根目录、默认 BVID 和通用参数解析 |
| `output_paths.py` | `output/` 目录结构、路径构造和查找 |
| `session.py` | 采集会话：缓存 cookie、WBI 密钥、视频信息和输出目录 |
| `main.py` | `bilibili` 命令行入口和功能分发 |
| `login.py` | 保存登录状态，并按 Chrome、Edge、Playwright Chromium 顺序启动浏览器 |
| `bilibili_api.py` | 公共接口请求、WBI 签名和字幕接口 |
| `crawler_info.py` | 获取并保存视频信息和 UP 主粉丝数 |
| `crawler_comment.py` | 分页采集全部一级评论并保存 CSV |
| `crawler_subtitle.py` | 下载字幕 JSON 并转换 SRT |
| `crawler_dm.py` | 使用 Playwright 采集弹幕 |
| `crawler_search.py` | 按关键词搜索视频并保存 CSV |
| `crawler_hot.py` | 遍历热搜词搜索视频 |
| `crawler_up.py` | 按 MID 采集 UP 主全部公开视频 |
| `crawler_common.py` | 爬虫共用的请求、并发、数据构建和文件输出 |
| `dm.proto` | 弹幕 Protobuf 结构定义 |
| `dm_pb2.py` | 根据 `dm.proto` 生成的 Python 代码 |
| `qt_app.py` | Qt 图形界面的兼容启动入口 |
| `qt_ui/app.py` | 创建 `QApplication` 并启动主窗口 |
| `qt_ui/main_window.py` | 主窗口、页面布局和爬虫任务控制 |
| `qt_ui/dialogs.py` | 表格预览和目录浏览弹窗 |
| `qt_ui/formatting.py` | 字段名称、数字和时间格式转换 |
| `qt_ui/theme.py` | 加载并注入 Qt 全局样式 |
| `assets/` | 图形界面资源，含图标、图片和 `app.qss` 样式表 |

## 环境要求

- Python 3.14 或更高版本
- Google Chrome、Microsoft Edge 或 Playwright Chromium
- 可访问 Bilibili 的网络环境
- 一个可正常登录的 Bilibili 账号(得到cookie)

程序使用 `zoneinfo` 把时间戳转换为中国时区时间。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

如果没有 Chrome 或 Edge，可以安装 Playwright 自带 Chromium：

```powershell
python -m playwright install chromium
```

依赖统一声明在 `pyproject.toml`。需要重新编译 `dm.proto` 时，
再安装开发依赖：

```powershell
pip install -e ".[dev]"
```

安装 Qt 图形界面依赖：

```powershell
pip install -e ".[gui]"
```

启动图形界面：

```powershell
bilibili-gui
```

也可以直接运行：

```powershell
python qt_app.py
```

## 运行

安装后所有命令都以 `bilibili` 开头，必须选择一项操作。
旧版 `python main.py` 和 `--subtitle-page` 等参数不再兼容。

确认登录状态：

```powershell
bilibili -l
```

只采集视频信息：

```powershell
bilibili -i BV1V3Yn6wENr
```

只采集一级评论：

```powershell
bilibili -c BV1V3Yn6wENr
```

按热门排序采集评论，每页 20 条：

```powershell
bilibili -c BV1V3Yn6wENr --comment-mode hot --comment-page-size 20
```

只采集字幕：

```powershell
bilibili -s BV1V3Yn6wENr
```

只采集字幕的指定分 P 范围和语言：

```powershell
bilibili -s BV1V3Yn6wENr -p 1,3 --language ai-zh
```

只采集弹幕：

```powershell
bilibili -d BV1V3Yn6wENr
```

只采集指定分 P 范围的弹幕：

```powershell
bilibili -d BV1V3Yn6wENr -p 1,3
```

按关键词搜索视频：

```powershell
bilibili -k "Python 教程"
```

通过 UP 主 MID 采集全部公开视频：

```powershell
bilibili -m 267068018
```

指定每次读取数量和并发线程数：

```powershell
bilibili -m 267068018 --page-size 50 -w 3
```

指定搜索页码范围、每页数量和并发线程数：

```powershell
bilibili -k "Python 教程" --search-page 2,4 --page-size 50 -w 3
```

关键词搜索中的单值页范围表示从第 1 页开始，例如 `--search-page 10`
表示采集第 1 到第 10 页；只采集第 10 页时使用 `--search-page 10,10`。

对 Bilibili 热搜词逐个执行搜索：

```powershell
bilibili -H
```

指定热搜数量：

```powershell
bilibili -H --limit 20
```

依次运行全部功能：

```powershell
bilibili -a BV1V3Yn6wENr
```

不填写 BV 号时，使用 `config.py` 中的 `DEFAULT_BVID`：

```powershell
bilibili -i
```

评论使用 WBI 游标分页顺序采集，不受旧评论接口的
`max offset exceeded` 页码上限影响。

首次运行或登录状态失效时，程序会打开可用浏览器，要求手动登录。
登录完成后，Cookie 和 localStorage 会保存到 `bilibili_state.json`。

`-a` 会依次执行：

1. 检查或刷新登录状态。
2. 保存视频信息和 UP 主粉丝数。
3. 下载该视频所有分 P 的字幕。
4. 打开播放器并采集所有分 P 的弹幕。
5. 最后按时间顺序下载该视频的全部一级评论（最慢，放在最后）。

评论、字幕和弹幕可能受以下条件影响：

- 评论数量较多时需要多次分页请求，采集时间会相应增加。
- 视频没有字幕时不会生成字幕文件。
- 部分高清晰度或字幕接口需要有效登录状态。
- 弹幕采集依赖播放器实际发出的请求，可能受网络和播放器策略影响。

## 输出目录

所有结果保存在 `output/` 下，按类别分成四个平级目录：

```text
output/
├── bvid/          视频数据
├── search/        关键词搜索
├── up/            UP 主视频
└── hot_search/    热搜搜索
```

视频数据保存在 `output/bvid/`：

```text
output/bvid/{UP主}_{标题}_{BV号}/
```

标题中的 `?`、`:`、`/`、`\` 等非法文件名字符会替换为 `_`。

典型目录内容：

```text
output/bvid/
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

搜索结果保存在：

```text
output/search/{关键词}/search_{时间}_{数据量}.csv
```

UP 主视频保存在：

```text
output/up/{MID}+{UP主名字}/videos_{时间}_{数据量}.csv
```

热搜搜索会按运行时间创建目录，并把每个热搜词的结果保存到对应子目录：

```text
output/hot_search/{运行时间}/{热搜词}/search_{时间}_{数据量}.csv
output/hot_search/{运行时间}/hot_list.csv
```

搜索 CSV 包含 `bvid`、标题、发布时间、作者、作者 mid、分区、标签、视频
时长、封面 URL、点赞数、评论数、收藏数、分享数、作者粉丝数、播放数和
弹幕数。除作者粉丝数外，其余字段直接来自搜索结果，不再批量请求视频详情；
作者粉丝数按作者 mid 缓存，同一作者只请求一次。搜索结果不提供分享数，
因此 `share_count` 固定为 `0`。搜索页和作者粉丝数请求使用线程池并发，
结果仍按搜索顺序保存。热搜词之间按榜单顺序串行处理，单个热搜词内部的
搜索请求仍按 `-w` 指定的并发数执行。

图形界面的数据预览支持直接打开视频：选中结果后点击“打开视频”，或双击
“视频编号”或“标题”单元格即可跳转到对应的 Bilibili 页面。为降低内存
占用，数据预览最多加载前 5000 行，完整数据仍保存在原始文件中。封面地址
列可单击打开封面，鼠标悬停时会显示链接反馈。GUI 关闭时会保存上次输入的
关键词、范围、并发数和工作区，重新打开后自动恢复对应的数据面板。

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
评论可以选择按时间或热门排序，通过 WBI 游标分页依次推进，并按照 `rpid`
去重。
接口返回的 `all_count` 是视频总评论数，包含一级评论下面的子评论；CSV
实际保存的行数是一级评论数。

每次运行都会从第一页开始完整采集当前可见的一级评论，并在成功后覆盖原有
CSV。任务中途失败时不会使用已有文件续传，下次运行会重新完整采集。

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
| `ip_location` | 评论 IP 属地，例如“湖北”；不是完整 IP 地址 |
| `image_urls` | 评论图片URL，多个地址用 `|` 分隔 |

图片只保存 URL，不下载图片文件。

命令行参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--comment-mode` | `time` | `time` 按时间排序，`hot` 按热门排序 |
| `--comment-page-size` | `30` | 评论每页数量，范围 `1-30` |

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
3. 登录无效时打开可用浏览器，等待人工登录。
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
