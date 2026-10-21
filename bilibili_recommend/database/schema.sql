CREATE DATABASE IF NOT EXISTS bilibili
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE bilibili;

CREATE TABLE IF NOT EXISTS videos (
    bvid             VARCHAR(32) PRIMARY KEY,
    aid              BIGINT DEFAULT 0,
    title            TEXT,
    description      TEXT,
    mid              BIGINT DEFAULT 0,
    published_at     DATETIME NULL,
    duration_seconds INT DEFAULT 0,
    tid              INT DEFAULT 0,
    partition_name   VARCHAR(64) DEFAULT '',
    cover_url        VARCHAR(512) DEFAULT '',
    view_count       BIGINT DEFAULT 0,
    like_count       BIGINT DEFAULT 0,
    coin_count       BIGINT DEFAULT 0,
    favorite_count   BIGINT DEFAULT 0,
    share_count      BIGINT DEFAULT 0,
    reply_count      BIGINT DEFAULT 0,
    danmaku_count    BIGINT DEFAULT 0,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_mid (mid),
    KEY idx_partition (partition_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS up_info (
    mid            BIGINT PRIMARY KEY,
    up_name        VARCHAR(255) DEFAULT '',
    face_url       VARCHAR(512) DEFAULT '',
    follower_count BIGINT DEFAULT 0,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS video_tags (
    id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    bvid VARCHAR(32) NOT NULL,
    tag  VARCHAR(255) NOT NULL,
    UNIQUE KEY uk_bvid_tag (bvid, tag),
    KEY idx_tag (tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS danmaku (
    id           BIGINT PRIMARY KEY,
    bvid         VARCHAR(32) NOT NULL,
    time_text    VARCHAR(32) DEFAULT '',
    time_seconds INT DEFAULT 0,
    weight       INT DEFAULT 1,
    content      TEXT,
    hash         VARCHAR(64) DEFAULT '',
    send_time    DATETIME NULL,
    pool         INT DEFAULT 0,
    KEY idx_bvid (bvid),
    KEY idx_bvid_time (bvid, time_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comments (
    rpid        BIGINT PRIMARY KEY,
    bvid        VARCHAR(32) NOT NULL,
    mid         BIGINT DEFAULT 0,
    user_name   VARCHAR(255) DEFAULT '',
    user_level  INT DEFAULT 0,
    sex         VARCHAR(16) DEFAULT '',
    vip         TINYINT DEFAULT 0,
    message     TEXT,
    ctime_text  VARCHAR(64) DEFAULT '',
    ctime       DATETIME NULL,
    like_count  BIGINT DEFAULT 0,
    reply_count BIGINT DEFAULT 0,
    state       INT DEFAULT 0,
    ip_location VARCHAR(64) DEFAULT '',
    image_urls  TEXT,
    KEY idx_bvid (bvid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subtitles (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    bvid       VARCHAR(32) NOT NULL,
    cid        BIGINT DEFAULT 0,
    page       INT DEFAULT 0,
    start_time DECIMAL(12, 3) DEFAULT 0,
    end_time   DECIMAL(12, 3) DEFAULT 0,
    content    TEXT,
    UNIQUE KEY uk_subtitle (bvid, cid, page, start_time),
    KEY idx_bvid (bvid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

