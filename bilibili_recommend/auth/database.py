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


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def ensure_tables():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(USERS_DDL)
            cursor.execute(LOGIN_ATTEMPTS_DDL)
        connection.commit()
    finally:
        connection.close()

