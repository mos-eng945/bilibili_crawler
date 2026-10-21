"""Backend auth configuration.

Reads MySQL settings from the shared database .env file.
"""

import os
from pathlib import Path


AUTH_DIR = Path(__file__).resolve().parent
ENV_FILE = AUTH_DIR.parent / "database" / ".env"


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


_load_env_file(ENV_FILE)


MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "bilibili"),
    "charset": os.environ.get("MYSQL_CHARSET", "utf8mb4"),
}


SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY",
    "dev-secret-key-change-me-please-32-bytes",
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


DEFAULT_AVATAR = os.environ.get(
    "DEFAULT_AVATAR",
    "https://example.com/default-avatar.png",
)

