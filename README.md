# Bilibili Crawler

本仓库包含 Bilibili 数据采集工具的 Python 后端与 Web 前端。

## 目录结构

| 目录 | 作用 |
| --- | --- |
| `bilibili/` | Python 命令行与 Qt 图形界面采集工具 |
| `crawler_web/` | Vue 3 + Vite Web 前端 |

## Python 采集工具

```powershell
cd bilibili
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[gui]"
```

详细说明见 [`bilibili/README.md`](bilibili/README.md)。

## Web 前端

需要 Node.js 22.18+ 或 24.12+：

```powershell
cd crawler_web
npm ci
npm run dev
```

详细说明见 [`crawler_web/README.md`](crawler_web/README.md)。
