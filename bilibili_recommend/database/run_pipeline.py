"""Run the full data pipeline: import -> clean -> analyze -> classify."""

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = BASE_DIR.parent / "analysis"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(ANALYSIS_DIR))


from config import OUTPUT_DIR  # noqa: E402
from db import ensure_database  # noqa: E402

import build_video_categories  # noqa: E402
import data_cleaning  # noqa: E402
import database_analysis  # noqa: E402
import import_video_files  # noqa: E402
import import_videos  # noqa: E402


def main():
    ensure_database()

    print("[1/4] 导入爬虫数据")
    import_videos.import_all(OUTPUT_DIR)
    import_video_files.import_all(OUTPUT_DIR)

    print("[2/4] 清洗弹幕和评论")
    data_cleaning.main()

    print("[3/4] 全库文本分析")
    database_analysis.main()

    print("[4/4] 视频分类")
    build_video_categories.main()

    print("数据流水线执行完成。")


if __name__ == "__main__":
    main()

