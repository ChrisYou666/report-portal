"""
从 SQL Server 读取 3 张维表，生成可在远程服务器执行的 SQL 脚本。

用法:
    python scripts/gen_dim_sync_sql.py
    python scripts/gen_dim_sync_sql.py --out dim_sync.sql

生成后上传并执行:
    scp dim_sync.sql root@<server>:/tmp/
    ssh root@<server> "docker exec -i postgresql psql -U portal -d report_portal -f /tmp/dim_sync.sql"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pyodbc

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
DEFAULT_OUT = REPO_ROOT / "scripts" / "dim_sync.sql"

DIM_TABLES = [
    ("STG_ZPAY_PROFILE", "sap_stg_zpay_profile"),
    ("STG_T001",         "sap_stg_t001"),
    ("STG_ZEST_ESTATE",  "sap_stg_zest_estate"),
]

ODS_SCHEMA = "ods"
BATCH_SIZE = 500


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出 SQL 文件路径")
    args = parser.parse_args()

    env = load_env(DEFAULT_ENV_PATH)
    conn_str = build_conn_str(env)

    print(f"连接 SQL Server ({env.get('SQLSERVER_HOST', '?')})...")
    conn = pyodbc.connect(conn_str, timeout=30)
    print("连接成功")

    lines: list[str] = [
        "-- ============================================================",
        "-- 维表同步脚本（STG_ZPAY_PROFILE / STG_T001 / STG_ZEST_ESTATE）",
        f"-- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        "-- 执行: psql -U portal -d report_portal -f dim_sync.sql",
        "-- ============================================================",
        "",
        "\\set ON_ERROR_STOP off",
        "CREATE SCHEMA IF NOT EXISTS ods;",
        "",
    ]

    total_rows = 0
    for src_table, ods_table in DIM_TABLES:
        rows, col_names = fetch_table(conn, src_table)
        col_str = ", ".join(col_names)
        full_table = f"{ODS_SCHEMA}.{ods_table}"

        lines.append(f"-- {src_table} -> {full_table}  ({len(rows)} rows)")
        # 将所有 character varying 列扩展为 text，避免长度超限
        lines.append(
            f"DO $$ DECLARE r record; BEGIN\n"
            f"  FOR r IN SELECT column_name FROM information_schema.columns\n"
            f"           WHERE table_schema='ods' AND table_name='{ods_table}'\n"
            f"             AND data_type='character varying'\n"
            f"  LOOP\n"
            f"    EXECUTE 'ALTER TABLE {full_table} ALTER COLUMN ' || quote_ident(r.column_name) || ' TYPE text';\n"
            f"  END LOOP;\n"
            f"END $$;"
        )
        lines.append(f"TRUNCATE TABLE {full_table};")

        if rows:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                values = ",\n  ".join(
                    "(" + ", ".join(sql_literal(v) for v in row) + ")"
                    for row in batch
                )
                lines.append(f"INSERT INTO {full_table} ({col_str}) VALUES")
                lines.append(f"  {values};")

        lines.append(f"-- {ods_table}: {len(rows)} rows written")
        lines.append("")
        total_rows += len(rows)
        print(f"  {src_table}: {len(rows)} 行")

    lines += [
        "-- 验证",
        "SELECT 'sap_stg_zpay_profile' AS tbl, count(*) FROM ods.sap_stg_zpay_profile",
        "UNION ALL SELECT 'sap_stg_t001',        count(*) FROM ods.sap_stg_t001",
        "UNION ALL SELECT 'sap_stg_zest_estate',  count(*) FROM ods.sap_stg_zest_estate;",
    ]

    args.out.write_text("\n".join(lines), encoding="utf-8")
    conn.close()

    size_kb = args.out.stat().st_size / 1024
    print(f"\n完成：{total_rows} 行，文件 {size_kb:.1f} KB -> {args.out}")
    print("\n上传并执行：")
    print(f"  scp {args.out} root@<服务器IP>:/tmp/dim_sync.sql")
    print("  ssh root@<服务器IP> \"docker exec -i postgresql psql -U portal -d report_portal -f /tmp/dim_sync.sql\"")


def fetch_table(conn: pyodbc.Connection, src_table: str) -> tuple[list, list[str]]:
    loaded_at = datetime.utcnow().isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION",
        src_table,
    )
    raw_cols = [r[0].lower() for r in cursor.fetchall()]
    if not raw_cols:
        print(f"  警告: {src_table} 列信息为空，跳过")
        return [], []

    col_names = ["_ods_loaded_at", "_source_table", "_row_hash"] + raw_cols
    select_cols = ", ".join(f"[{c.upper()}]" for c in raw_cols)
    cursor.execute(f"SELECT {select_cols} FROM dbo.{src_table}")

    rows = []
    for raw_row in cursor.fetchall():
        vals = [to_str(v) for v in raw_row]
        row_hash = hashlib.sha256("|".join(v or "" for v in vals).encode()).hexdigest()
        rows.append([loaded_at, src_table, row_hash] + vals)

    return rows, col_names


def to_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, bytes):
        return v.hex()
    s = str(v).strip()
    return s if s else None


def sql_literal(v) -> str:
    if v is None:
        return "NULL"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_conn_str(env: dict[str, str]) -> str:
    direct = env.get("SQLSERVER_CONNECTION_STRING", "")
    if direct:
        return direct
    host     = env.get("SQLSERVER_HOST", "")
    port     = env.get("SQLSERVER_PORT", "1433")
    database = env.get("SQLSERVER_DATABASE", "")
    user     = env.get("SQLSERVER_USER", "")
    password = env.get("SQLSERVER_PASSWORD", "")
    driver   = env.get("SQLSERVER_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    encrypt  = env.get("SQLSERVER_ENCRYPT", "yes")
    trust    = env.get("SQLSERVER_TRUST_SERVER_CERTIFICATE", "yes")
    if not host or not database:
        raise RuntimeError("缺少 SQLSERVER_HOST / SQLSERVER_DATABASE 配置，请检查 backend/.env")
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};PWD={password};"
        f"Encrypt={encrypt};TrustServerCertificate={trust};"
    )


if __name__ == "__main__":
    main()
