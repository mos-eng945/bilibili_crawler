"""把 CSV/JSON/SRT 文件读成表格数据。

所有读取函数统一返回 `(raw_headers, headers, rows, truncated)`：
原始列名、显示用的中文列名、行数据，以及是否因为超限被截断。
放在这里既方便复用，也便于脱离界面单独测试。
"""

import csv
import json
import re
from pathlib import Path

from qt_ui.dialogs.constants import PREVIEW_ROW_LIMIT
from qt_ui.formatting import COLUMN_LABELS


def load_preview(path):
    """按扩展名读取预览数据，未知类型返回空的「字段/内容」两列。"""
    path = Path(path)
    reader = _READERS.get(path.suffix.lower())

    if reader is None:
        return ["字段", "内容"], ["字段", "内容"], [], False

    return reader(path)


def _read_csv(path):
    rows = []
    truncated = False

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        raw_headers = reader.fieldnames or []
        headers = [
            COLUMN_LABELS.get(header, header) for header in raw_headers
        ]

        for row in reader:
            if len(rows) >= PREVIEW_ROW_LIMIT:
                truncated = True
                break

            rows.append(
                [
                    str(row.get(header) or "").replace("\x00", "")
                    for header in raw_headers
                ]
            )

    return raw_headers, headers, rows, truncated


def _read_json(path):
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict) and isinstance(data.get("subtitle"), dict):
        return _read_subtitle(data["subtitle"])

    if not isinstance(data, dict):
        return ["字段", "内容"], ["字段", "内容"], [], False

    raw_headers = list(data.keys())
    headers = [COLUMN_LABELS.get(key, key) for key in raw_headers]
    row = []

    for key in raw_headers:
        value = data.get(key)

        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)

        row.append(value)

    return raw_headers, headers, [row], False


def _read_subtitle(subtitle):
    body = subtitle.get("body") or []
    raw_headers = ["序号", "开始", "结束", "字幕内容"]
    headers = ["序号", "开始时间", "结束时间", "字幕内容"]
    rows = []
    truncated = False

    for index, item in enumerate(body, start=1):
        if len(rows) >= PREVIEW_ROW_LIMIT:
            truncated = True
            break

        rows.append(
            [
                index,
                item.get("from", 0),
                item.get("to", 0),
                item.get("content", ""),
            ]
        )

    return raw_headers, headers, rows, truncated


def _read_srt(path):
    """把 SRT 字幕拆成序号/开始/结束/内容四列。"""
    raw_headers = ["序号", "开始", "结束", "字幕内容"]
    headers = ["序号", "开始时间", "结束时间", "字幕内容"]
    rows = []
    truncated = False
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        if len(rows) >= PREVIEW_ROW_LIMIT:
            truncated = True
            break

        lines = [line for line in block.splitlines() if line.strip()]

        if len(lines) < 3:
            continue

        match = re.match(r"(.+?)\s*-->\s*(.+)", lines[1])
        start, end = (
            (match.group(1).strip(), match.group(2).strip())
            if match
            else ("", "")
        )
        rows.append([len(rows) + 1, start, end, "\n".join(lines[2:])])

    return raw_headers, headers, rows, truncated


_READERS = {
    ".csv": _read_csv,
    ".json": _read_json,
    ".srt": _read_srt,
}
