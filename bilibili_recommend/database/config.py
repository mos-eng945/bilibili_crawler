"""MySQL connection and crawler output paths.

Secrets are read from environment variables or a local ``.env`` file.
The ``.env`` file should not be committed to version control.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / ".env")


MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "bilibili"),
    "charset": os.environ.get("MYSQL_CHARSET", "utf8mb4"),
}


CRAWLER_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(
    os.environ.get(
        "BILIBILI_OUTPUT_DIR",
        CRAWLER_ROOT.parent / "bilibili" / "output",
    )
)


