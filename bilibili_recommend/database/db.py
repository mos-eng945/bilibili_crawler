"""Helpers for connecting to MySQL."""

import pymysql

from config import MYSQL_CONFIG


def ensure_database():
    """Create the target database if it does not exist."""
    config = MYSQL_CONFIG.copy()
    database = config.pop("database")

    connection = pymysql.connect(**config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS `%s` "
                "DEFAULT CHARACTER SET utf8mb4 "
                "DEFAULT COLLATE utf8mb4_unicode_ci" % database
            )
        connection.commit()
    finally:
        connection.close()


def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)

