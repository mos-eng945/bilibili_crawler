"""Database helpers for the auth backend."""

import pymysql

from config import MYSQL_CONFIG


USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    avatar        VARCHAR(512) DEFAULT '',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


LOGIN_ATTEMPTS_DDL = """
CREATE TABLE IF NOT EXISTS login_attempts (
    username     VARCHAR(20) PRIMARY KEY,
    fail_count   INT DEFAULT 0,
    locked_until DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


FAVORITES_DDL = """
CREATE TABLE IF NOT EXISTS favorites (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    bvid       VARCHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_bvid (user_id, bvid),
    KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


SEARCH_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS search_history (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    keyword     VARCHAR(200) DEFAULT '',
    category_id VARCHAR(64) DEFAULT '',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def ensure_tables():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(USERS_DDL)
            cursor.execute(LOGIN_ATTEMPTS_DDL)
            cursor.execute(FAVORITES_DDL)
            cursor.execute(SEARCH_HISTORY_DDL)
        connection.commit()
    finally:
        connection.close()

