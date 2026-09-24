"""项目级默认配置和通用参数解析。"""

import argparse


DEFAULT_BVID = "BV1UT42167xb"


def parse_page_range(value):
    """把 START 或 START,END 转换成包含首尾的整数范围。"""
    parts = value.split(",")

    if len(parts) > 2:
        raise argparse.ArgumentTypeError("范围格式应为 START,END")

    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) == 2 else start
    except ValueError as exc:
        raise argparse.ArgumentTypeError("页码范围必须是整数") from exc

    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("页码必须满足 1 <= START <= END")

    return start, end
