"""
pg_to_mysql.py
--------------
从 PostgreSQL 抽取 indicator 相关表和用户主数据，生成 MySQL 兼容的 INSERT 脚本。

运行方式（在 backend 目录下）：
    python pg_to_mysql.py

生成文件：pg_to_mysql_export.sql
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

# ── 加载 .env ──────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.environ.get("database_url", "postgresql+psycopg://portal:portal@127.0.0.1:5432/report_portal"),
)

# 把 SQLAlchemy URL 转成 psycopg DSN
dsn = re.sub(r"^postgresql\+psycopg://", "postgresql://", DATABASE_URL)

try:
    import psycopg
except ImportError:
    print("需要 psycopg：pip install psycopg")
    sys.exit(1)

# ── 要导出的表（按依赖顺序） ────────────────────────────────────
TABLES = [
    "users",
    "index_definitions",
    "index_sub_metrics",
    "index_data_entries",
    "system_configs",
    "scheduled_syncs",
]

# ── MySQL DDL 定义 ─────────────────────────────────────────────
DDL = {
    "users": """
CREATE TABLE IF NOT EXISTS `users` (
  `id`            INT            NOT NULL AUTO_INCREMENT,
  `username`      VARCHAR(80)    NOT NULL,
  `password_hash` VARCHAR(255)   NOT NULL,
  `display_name`  VARCHAR(120)   NOT NULL DEFAULT '',
  `role`          VARCHAR(40)    NOT NULL DEFAULT 'viewer',
  `department`    VARCHAR(120)   NOT NULL DEFAULT '',
  `site`          VARCHAR(120)   NOT NULL DEFAULT '',
  `is_active`     TINYINT(1)     NOT NULL DEFAULT 1,
  `created_at`    DATETIME       NOT NULL,
  `updated_at`    DATETIME       NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "index_definitions": """
CREATE TABLE IF NOT EXISTS `index_definitions` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `code`        VARCHAR(40)  NOT NULL,
  `name`        VARCHAR(120) NOT NULL,
  `formula`     TEXT         NOT NULL,
  `description` TEXT         NOT NULL,
  `sort_order`  INT          NOT NULL DEFAULT 0,
  `is_active`   TINYINT(1)   NOT NULL DEFAULT 1,
  `granularity` VARCHAR(20)  NOT NULL DEFAULT 'monthly',
  `created_at`  DATETIME     NOT NULL,
  `updated_at`  DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_index_definitions_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "index_sub_metrics": """
CREATE TABLE IF NOT EXISTS `index_sub_metrics` (
  `id`                  INT          NOT NULL AUTO_INCREMENT,
  `index_id`            INT          NOT NULL,
  `code`                VARCHAR(40)  NOT NULL,
  `name`                VARCHAR(120) NOT NULL DEFAULT '',
  `unit`                VARCHAR(40)  NOT NULL DEFAULT '',
  `source_type`         VARCHAR(20)  NOT NULL DEFAULT 'manual',
  `fixed_value`         DOUBLE,
  `db_table`            VARCHAR(120),
  `db_field`            VARCHAR(120),
  `db_aggregation`      VARCHAR(20)  NOT NULL DEFAULT 'SUM',
  `db_date_col`         VARCHAR(120) NOT NULL DEFAULT 'report_date',
  `db_extra_where`      TEXT NULL,
  `fiscal_start_month`  INT,
  `sort_order`          INT          NOT NULL DEFAULT 0,
  `created_at`          DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_index_sub_metrics_index_id` (`index_id`),
  CONSTRAINT `fk_sub_metrics_index_id` FOREIGN KEY (`index_id`) REFERENCES `index_definitions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "index_data_entries": """
CREATE TABLE IF NOT EXISTS `index_data_entries` (
  `id`             INT          NOT NULL AUTO_INCREMENT,
  `sub_metric_id`  INT          NOT NULL,
  `period_year`    INT          NOT NULL,
  `period_month`   INT          NOT NULL,
  `value`          DOUBLE,
  `source`         VARCHAR(40)  NOT NULL DEFAULT 'manual',
  `remark`         TEXT         NOT NULL,
  `created_by`     VARCHAR(120) NOT NULL DEFAULT '',
  `created_at`     DATETIME     NOT NULL,
  `updated_at`     DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_index_data_entry` (`sub_metric_id`, `period_year`, `period_month`),
  CONSTRAINT `fk_data_entries_sub_metric_id` FOREIGN KEY (`sub_metric_id`) REFERENCES `index_sub_metrics` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "system_configs": """
CREATE TABLE IF NOT EXISTS `system_configs` (
  `key`        VARCHAR(120) NOT NULL,
  `value`      TEXT         NOT NULL,
  `updated_by` VARCHAR(120) NOT NULL DEFAULT '',
  `updated_at` DATETIME     NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    "scheduled_syncs": """
CREATE TABLE IF NOT EXISTS `scheduled_syncs` (
  `id`            INT          NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(120) NOT NULL,
  `sync_type`     VARCHAR(40)  NOT NULL,
  `sub_metric_id` INT,
  `months`        INT          NOT NULL DEFAULT 12,
  `cron_minute`   VARCHAR(20)  NOT NULL DEFAULT '0',
  `cron_hour`     VARCHAR(20)  NOT NULL DEFAULT '2',
  `cron_day`      VARCHAR(20)  NOT NULL DEFAULT '*',
  `cron_month`    VARCHAR(20)  NOT NULL DEFAULT '*',
  `cron_dow`      VARCHAR(20)  NOT NULL DEFAULT '*',
  `enabled`       TINYINT(1)   NOT NULL DEFAULT 1,
  `last_run_at`   DATETIME,
  `last_status`   VARCHAR(20),
  `last_message`  TEXT,
  `created_by`    VARCHAR(120) NOT NULL DEFAULT '',
  `created_at`    DATETIME     NOT NULL,
  `updated_at`    DATETIME     NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
}


# ── 值转义 ─────────────────────────────────────────────────────
def escape(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(val, datetime) else val}'"
    # 字符串：转义单引号和反斜杠
    s = str(val).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


# ── 主逻辑 ─────────────────────────────────────────────────────
def main():
    out = Path(__file__).parent / "pg_to_mysql_export.sql"
    lines: list[str] = []

    lines.append("-- ============================================================")
    lines.append(f"-- PostgreSQL → MySQL 导出  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-- 表：users, index_definitions, index_sub_metrics,")
    lines.append("--      index_data_entries, system_configs, scheduled_syncs")
    lines.append("-- ============================================================")
    lines.append("")
    lines.append("SET NAMES utf8mb4;")
    lines.append("SET FOREIGN_KEY_CHECKS = 0;")
    lines.append("")

    try:
        conn = psycopg.connect(dsn)
    except Exception as e:
        print(f"连接 PostgreSQL 失败：{e}")
        sys.exit(1)

    with conn:
        cur = conn.cursor()

        for table in TABLES:
            lines.append(f"-- ── {table} {'─' * (50 - len(table))}")
            lines.append("")

            # DDL
            if table in DDL:
                lines.append(f"DROP TABLE IF EXISTS `{table}`;")
                lines.append(DDL[table].strip())
                lines.append("")

            # 获取列名
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position",
                (table,),
            )
            columns = [r[0] for r in cur.fetchall()]
            if not columns:
                print(f"  警告：表 {table} 不存在或无列，跳过")
                continue

            # 抽数据
            col_select = ", ".join('"' + c + '"' for c in columns)
            cur.execute(f'SELECT {col_select} FROM "{table}" ORDER BY 1')
            rows = cur.fetchall()

            if not rows:
                lines.append(f"-- （{table} 暂无数据）")
                lines.append("")
                print(f"  {table}: 0 行")
                continue

            col_list = ", ".join(f"`{c}`" for c in columns)
            batch: list[str] = []

            for row in rows:
                vals = ", ".join(escape(v) for v in row)
                batch.append(f"  ({vals})")

                # 每 200 行一个 INSERT 语句
                if len(batch) >= 200:
                    lines.append(f"INSERT INTO `{table}` ({col_list}) VALUES")
                    lines.append(",\n".join(batch) + ";")
                    lines.append("")
                    batch = []

            if batch:
                lines.append(f"INSERT INTO `{table}` ({col_list}) VALUES")
                lines.append(",\n".join(batch) + ";")
                lines.append("")

            print(f"  {table}: {len(rows)} 行")

    lines.append("")
    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    lines.append("")
    lines.append("-- 导出完成")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 已生成：{out}")


if __name__ == "__main__":
    main()
