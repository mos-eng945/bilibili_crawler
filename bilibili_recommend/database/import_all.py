"""Run the full import pipeline."""

import sys
from pathlib import Path

from config import OUTPUT_DIR
from db import ensure_database
from import_video_files import import_all as import_files
from import_videos import import_all as import_videos


def main():
    ensure_database()
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_DIR
    import_videos(output_dir)
    import_files(output_dir)
    print("All imports finished.")


if __name__ == "__main__":
    main()

