from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional

import psycopg


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
DEFAULT_ETL_DIR = REPO_ROOT / "ETLs"
ODS_SCHEMA = "ods"
DATE_FILTER_COLUMNS = {
    "STG_ZEST_BLOCKC": ("CRDAT", "date"),
    "STG_ZPAY_WORK": ("BUDAT", "date"),
    "STG_ZEST_NOSPB": ("BUDAT", "date"),
    "STG_ZPAY_BCC": ("BUDAT", "date"),
    "STG_ZEST_HARV": ("BUDAT", "date"),
    "STG_ZEST_BLOCKB": ("SPMON", "period"),
    "STG_ZEST_BLOCKH": ("SPMON", "period"),
    "STG_ZEST_BLOCKP": ("MUNTH", "period"),
    "STG_COSP": ("GJAHR", "year"),
}


def main() -> None:
    args = parse_args()
    env = load_env(DEFAULT_ENV_PATH)

    etl_files = resolve_etl_files(args.etl_dir, args.only)
    dependency_map = collect_source_table_dependencies(etl_files)
    source_tables = sorted({table for tables in dependency_map.values() for table in tables})
    if args.tables:
        requested_tables = {item.strip().upper() for item in args.tables.split(",") if item.strip()}
        source_tables = sorted(requested_tables)
    cutoff_date = resolve_cutoff_date(args)

    if args.list:
        print("ETL SQL dependencies:")
        for etl_file in etl_files:
            tables = dependency_map.get(etl_file.name, [])
            print(f"- {etl_file.name}: {', '.join(tables)}")
        print("\nODS source table targets:")
        for source_table in source_tables:
            print(f"- {source_table} -> {ODS_SCHEMA}.{target_table_name(source_table)} {filter_summary(source_table, cutoff_date)}")
        return

    if args.mode == "replace" and not args.yes:
        raise SystemExit("replace 模式会重建 ODS 目标表。确认执行请增加 --yes。")
    if not source_tables:
        raise SystemExit("没有解析到需要抽取的 SAP/STG 原表。")

    sqlserver_connection_string = build_sqlserver_connection_string(env)
    postgres_dsn = normalize_postgres_dsn(get_config("DATABASE_URL", env, required=True))

    import pyodbc

    with pyodbc.connect(sqlserver_connection_string, autocommit=True) as sqlserver_conn:
        with psycopg.connect(postgres_dsn) as postgres_conn:
            ensure_ods_schema(postgres_conn)
            record_dependency_map(postgres_conn, dependency_map)
            for source_table in source_tables:
                sync_one_source_table(
                    sqlserver_conn=sqlserver_conn,
                    postgres_conn=postgres_conn,
                    source_table=source_table,
                    mode=args.mode,
                    batch_size=args.batch_size,
                    top_rows=args.top,
                    cutoff_date=cutoff_date,
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 ETLs/*.sql 解析依赖的 SAP/STG 原表，并从 SQL Server 抽取原表快照到 PostgreSQL ods schema。"
    )
    parser.add_argument("--etl-dir", type=Path, default=DEFAULT_ETL_DIR, help="SQL 文件目录，默认 ETLs/")
    parser.add_argument(
        "--only",
        default="",
        help="只同步指定 SQL 文件，逗号分隔。例：--only produksi_janjang.sql,losses.sql",
    )
    parser.add_argument(
        "--tables",
        default="",
        help="只抽取指定 SAP/STG 原表，逗号分隔。例：--tables STG_ZEST_BLOCKC,STG_ZPAY_WORK",
    )
    parser.add_argument("--mode", choices=["replace", "append"], default="replace", help="replace 重建表，append 追加数据")
    parser.add_argument("--batch-size", type=int, default=1000, help="每批写入行数")
    parser.add_argument("--top", type=int, default=0, help="测试用：每张原表最多抽取前 N 行，0 表示不限制")
    parser.add_argument("--months", type=int, default=2, help="事实表抽取最近 N 个月，默认 2")
    parser.add_argument("--since", default="", help="事实表抽取起始日期，格式 YYYY-MM-DD；优先级高于 --months")
    parser.add_argument("--list", action="store_true", help="只列出 ETL 依赖的原表和目标 ODS 表，不连接数据库")
    parser.add_argument("--yes", action="store_true", help="确认执行 replace 模式")
    return parser.parse_args()


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


def get_config(name: str, env: dict[str, str], required: bool = False, default: str = "") -> str:
    value = os.environ.get(name) or env.get(name) or default
    if required and not value:
        raise RuntimeError(f"缺少配置：{name}")
    return value


def build_sqlserver_connection_string(env: dict[str, str]) -> str:
    direct = get_config("SQLSERVER_CONNECTION_STRING", env)
    if direct:
        return direct

    host = get_config("SQLSERVER_HOST", env, required=True)
    port = get_config("SQLSERVER_PORT", env, default="1433")
    database = get_config("SQLSERVER_DATABASE", env, required=True)
    user = get_config("SQLSERVER_USER", env, required=True)
    password = get_config("SQLSERVER_PASSWORD", env, required=True)
    driver = get_config("SQLSERVER_ODBC_DRIVER", env, default="ODBC Driver 17 for SQL Server")
    trust_cert = get_config("SQLSERVER_TRUST_SERVER_CERTIFICATE", env, default="yes")
    encrypt = get_config("SQLSERVER_ENCRYPT", env, default="yes")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
    )


def normalize_postgres_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://", 1)


def resolve_etl_files(etl_dir: Path, only: str) -> list[Path]:
    etl_dir = etl_dir if etl_dir.is_absolute() else REPO_ROOT / etl_dir
    if not etl_dir.exists():
        raise RuntimeError(f"ETL 目录不存在：{etl_dir}")

    files = sorted(etl_dir.glob("*.sql"))
    if only:
        requested = {item.strip().lower() for item in only.split(",") if item.strip()}
        files = [path for path in files if path.name.lower() in requested or path.stem.lower() in requested]
    if not files:
        raise RuntimeError("没有找到需要同步的 SQL 文件。")
    return files


def ensure_ods_schema(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"create schema if not exists {quote_ident(ODS_SCHEMA)}")
        cursor.execute(
            f"""
            create table if not exists {quote_ident(ODS_SCHEMA)}.sap_ingestion_runs (
                id bigserial primary key,
                source_file text not null,
                target_table text not null,
                mode text not null,
                row_count bigint not null,
                started_at timestamptz not null,
                finished_at timestamptz not null,
                status text not null,
                error_message text default ''
            )
            """
        )
        cursor.execute(
            f"""
            create table if not exists {quote_ident(ODS_SCHEMA)}.sap_source_table_dependencies (
                etl_file text not null,
                source_table text not null,
                target_table text not null,
                detected_at timestamptz not null,
                primary key (etl_file, source_table)
            )
            """
        )
    connection.commit()


def record_dependency_map(connection: psycopg.Connection, dependency_map: dict[str, list[str]]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"delete from {quote_ident(ODS_SCHEMA)}.sap_source_table_dependencies")
        rows = [
            (etl_file, source_table, target_table_name(source_table), datetime.utcnow())
            for etl_file, tables in dependency_map.items()
            for source_table in tables
        ]
        cursor.executemany(
            f"""
            insert into {quote_ident(ODS_SCHEMA)}.sap_source_table_dependencies
            (etl_file, source_table, target_table, detected_at)
            values (%s, %s, %s, %s)
            """,
            rows,
        )
    connection.commit()


def sync_one_source_table(
    *,
    sqlserver_conn: Any,
    postgres_conn: psycopg.Connection,
    source_table: str,
    mode: str,
    batch_size: int,
    top_rows: int,
    cutoff_date: date,
) -> None:
    started_at = datetime.utcnow()
    target_table = target_table_name(source_table)
    top_clause = f"top ({top_rows}) " if top_rows > 0 else ""
    sql_text = f"select {top_clause}* from {sqlserver_table_ref(source_table)}{where_clause(source_table, cutoff_date)}"
    row_count = 0

    print(f"SYNC {source_table} -> {ODS_SCHEMA}.{target_table} {filter_summary(source_table, cutoff_date)}", flush=True)
    try:
        source_cursor = sqlserver_conn.cursor()
        source_cursor.execute(sql_text)
        column_names = make_unique_column_names([column[0] for column in source_cursor.description or []])
        if not column_names:
            raise RuntimeError(f"{etl_file.name} 没有返回列。")

        prepare_target_table(postgres_conn, target_table, column_names, mode)
        while True:
            rows = source_cursor.fetchmany(batch_size)
            if not rows:
                break
            insert_rows(postgres_conn, target_table, source_table, column_names, rows)
            row_count += len(rows)
            print(f"  inserted {row_count}", flush=True)
        record_run(postgres_conn, source_table, target_table, mode, row_count, started_at, "success", "")
        postgres_conn.commit()
        print(f"DONE {source_table}: {row_count} rows", flush=True)
    except Exception as exc:
        postgres_conn.rollback()
        record_run(postgres_conn, source_table, target_table, mode, row_count, started_at, "failed", str(exc))
        postgres_conn.commit()
        raise


def prepare_target_table(
    connection: psycopg.Connection,
    table_name: str,
    column_names: list[str],
    mode: str,
) -> None:
    full_table = f"{quote_ident(ODS_SCHEMA)}.{quote_ident(table_name)}"
    with connection.cursor() as cursor:
        if mode == "replace":
            cursor.execute(f"drop table if exists {full_table}")
        columns_sql = ",\n".join(f"{quote_ident(column)} text" for column in column_names)
        cursor.execute(
            f"""
            create table if not exists {full_table} (
                _ods_loaded_at timestamptz not null,
                _source_table text not null,
                _row_hash text not null,
                {columns_sql}
            )
            """
        )


def insert_rows(
    connection: psycopg.Connection,
    table_name: str,
    source_file: str,
    column_names: list[str],
    rows: Iterable[Any],
) -> None:
    full_table = f"{quote_ident(ODS_SCHEMA)}.{quote_ident(table_name)}"
    all_columns = ["_ods_loaded_at", "_source_table", "_row_hash", *column_names]
    placeholders = ", ".join(["%s"] * len(all_columns))
    columns_sql = ", ".join(quote_ident(column) for column in all_columns)
    sql = f"insert into {full_table} ({columns_sql}) values ({placeholders})"
    loaded_at = datetime.utcnow()
    values = []
    for row in rows:
        row_values = [to_text(value) for value in row]
        values.append([loaded_at, source_file, row_hash(row_values), *row_values])
    with connection.cursor() as cursor:
        cursor.executemany(sql, values)


def record_run(
    connection: psycopg.Connection,
    source_file: str,
    target_table: str,
    mode: str,
    row_count: int,
    started_at: datetime,
    status: str,
    error_message: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            insert into {quote_ident(ODS_SCHEMA)}.sap_ingestion_runs
            (source_file, target_table, mode, row_count, started_at, finished_at, status, error_message)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (source_file, target_table, mode, row_count, started_at, datetime.utcnow(), status, error_message[:1000]),
        )


def collect_source_table_dependencies(etl_files: list[Path]) -> dict[str, list[str]]:
    return {
        etl_file.name: extract_source_tables(etl_file.read_text(encoding="utf-8-sig"))
        for etl_file in etl_files
    }


def extract_source_tables(sql_text: str) -> list[str]:
    cleaned = strip_sql_comments(sql_text)
    candidates = re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_.$\[\]]*)", cleaned, flags=re.IGNORECASE)
    tables: list[str] = []
    for candidate in candidates:
        table_name = candidate.strip().strip("[]").upper()
        if table_name.startswith("STG_") or ".STG_" in table_name:
            tables.append(table_name)
    return sorted(set(tables))


def strip_sql_comments(sql_text: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    return re.sub(r"--.*?$", " ", without_block_comments, flags=re.MULTILINE)


def target_table_name(source_table: str) -> str:
    table_part = source_table.split(".")[-1]
    return "sap_" + normalize_identifier(table_part)


def sqlserver_table_ref(source_table: str) -> str:
    return ".".join(f"[{part.strip('[]')}]" for part in source_table.split("."))


def resolve_cutoff_date(args: argparse.Namespace) -> date:
    if args.since:
        return date.fromisoformat(args.since)
    return add_months(date.today(), -args.months)


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    days_in_month = [31, 29 if is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(value.day, days_in_month[month - 1])
    return date(year, month, day)


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def where_clause(source_table: str, cutoff_date: date) -> str:
    filter_config = DATE_FILTER_COLUMNS.get(source_table.upper())
    if not filter_config:
        return ""
    column, filter_type = filter_config
    if filter_type == "period":
        return f" where try_convert(int, [{column}]) >= {cutoff_date:%Y%m}"
    if filter_type == "year":
        return f" where try_convert(int, [{column}]) >= {cutoff_date.year}"
    return (
        f" where coalesce(try_convert(date, [{column}]), try_convert(date, [{column}], 112)) "
        f">= '{cutoff_date.isoformat()}'"
    )


def filter_summary(source_table: str, cutoff_date: date) -> str:
    filter_config = DATE_FILTER_COLUMNS.get(source_table.upper())
    if not filter_config:
        return "(full snapshot)"
    column, filter_type = filter_config
    if filter_type == "period":
        return f"(filtered: {column} >= {cutoff_date:%Y%m})"
    if filter_type == "year":
        return f"(filtered: {column} >= {cutoff_date.year})"
    return f"(filtered: {column} >= {cutoff_date.isoformat()})"


def make_unique_column_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        normalized = normalize_identifier(name or "column")
        count = seen.get(normalized, 0) + 1
        seen[normalized] = count
        result.append(normalized if count == 1 else f"{normalized}_{count}")
    return result


def normalize_identifier(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        value = "value"
    if value[0].isdigit():
        value = "c_" + value
    return value


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def to_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def row_hash(row_values: list[Optional[str]]) -> str:
    payload = json.dumps(row_values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
