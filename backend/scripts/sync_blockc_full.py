"""
全量同步 SQL Server STG_ZEST_BLOCKC → PostgreSQL ods.sap_stg_zest_blockc
然后重建 dwd.sap_harvest_actual_block_daily

用法:
  python scripts/sync_blockc_full.py            # 全量
  python scripts/sync_blockc_full.py --months 2  # 近 N 个月（增量）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from datetime import date, datetime, timedelta

import psycopg
import pyodbc
from psycopg import sql as psql

MSSQL_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=192.168.12.26,1433;"
    "Database=DWH-ASP;"
    "UID=jl_bigdata;PWD=Julong2026;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)
PG_DSN = "postgresql://portal:portal@127.0.0.1:5432/report_portal"

ODS_TABLE  = "sap_stg_zest_blockc"
ODS_SCHEMA = "ods"
SRC_TABLE  = "STG_ZEST_BLOCKC"
BATCH_SIZE = 5000


def normalize(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\x00", "").replace("\r", "").replace("\n", " ")


def get_src_columns(src) -> list[str]:
    rows = src.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION",
        SRC_TABLE,
    ).fetchall()
    return [r[0].lower() for r in rows]


def sync_ods(src, pg, cols: list[str], where_sql: str = "") -> int:
    now_str = datetime.utcnow().isoformat()
    all_cols = cols + ["_ods_loaded_at", "_source_table", "_row_hash"]

    if where_sql:
        # 增量：只删本次范围再插
        print(f"  增量模式，删除旧数据: {where_sql}")
        with pg.cursor() as c:
            c.execute(f"DELETE FROM {ODS_SCHEMA}.{ODS_TABLE} WHERE {where_sql}")
        pg.commit()
    else:
        print("  全量模式，清空 ODS 表")
        with pg.cursor() as c:
            c.execute(f"TRUNCATE TABLE {ODS_SCHEMA}.{ODS_TABLE}")
        pg.commit()

    select_cols = ", ".join(f"[{c.upper()}]" for c in cols)
    full_where  = f"WHERE {where_sql}" if where_sql else ""
    src_cur = src.cursor()
    src_cur.execute(f"SELECT {select_cols} FROM dbo.{SRC_TABLE} {full_where}")

    copy_stmt = psql.SQL(
        "COPY {schema}.{table} ({fields}) FROM STDIN WITH (FORMAT csv, NULL '')"
    ).format(
        schema=psql.Identifier(ODS_SCHEMA),
        table=psql.Identifier(ODS_TABLE),
        fields=psql.SQL(", ").join(psql.Identifier(c) for c in all_cols),
    )

    total = 0
    with pg.cursor() as pgc:
        with pgc.copy(copy_stmt) as copy:
            while True:
                rows = src_cur.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                buf = io.StringIO()
                writer = csv.writer(buf, lineterminator="\n")
                for row in rows:
                    vals = [normalize(v) for v in row]
                    row_hash = hashlib.sha256("|".join(vals).encode()).hexdigest()
                    writer.writerow(vals + [now_str, SRC_TABLE, row_hash])
                copy.write(buf.getvalue())
                total += len(rows)
                if total % 50_000 == 0:
                    print(f"  已写入 {total:,} 行…")
    pg.commit()
    return total


def rebuild_dwd(pg) -> int:
    """从 ODS 重建 dwd.sap_harvest_actual_block_daily。"""
    print("重建 DWD…")
    # TRUNCATE 单独提交，避免和 INSERT 同事务冲突
    with pg.cursor() as c:
        c.execute("TRUNCATE TABLE dwd.sap_harvest_actual_block_daily")
    pg.commit()

    with pg.cursor() as c:
        c.execute("""
            INSERT INTO dwd.sap_harvest_actual_block_daily
              (date, estate_code, estate_name, division_code, division_name,
               block_code, block_name, production_bg, production_ag,
               unit, source_system, source_table, source_row_count,
               quality_status, built_at)
            SELECT
              crdat::date,
              estnr,
              '', '', '',
              block,
              '',
              SUM(CASE WHEN qreal ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN qreal::numeric ELSE 0 END),
              SUM(CASE WHEN ntqty ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN ntqty::numeric ELSE 0 END),
              'kg', 'SAP', 'ods.sap_stg_zest_blockc', COUNT(*), 'ok', NOW()
            FROM ods.sap_stg_zest_blockc
            WHERE crdat ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            GROUP BY crdat::date, estnr, block
        """)
        count = c.rowcount
    pg.commit()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=0,
                        help="0=全量，N=近N个月增量")
    args = parser.parse_args()

    print(f"连接 SQL Server ({MSSQL_CONN.split(';')[1]})…")
    src = pyodbc.connect(MSSQL_CONN, timeout=30)
    print(f"连接 PostgreSQL…")
    pg  = psycopg.connect(PG_DSN)

    cols = get_src_columns(src)
    print(f"字段数: {len(cols)}")

    if args.months > 0:
        cutoff = (date.today() - timedelta(days=args.months * 31)).isoformat()
        where  = f"CRDAT >= '{cutoff}'"
        print(f"增量模式: {where}")
    else:
        where = ""
        print("全量模式: 拉取所有数据")

    ods_rows = sync_ods(src, pg, cols, where)
    print(f"ODS 写入: {ods_rows:,} 行")

    dwd_rows = rebuild_dwd(pg)
    print(f"DWD 重建: {dwd_rows:,} 行")

    src.close()
    pg.close()
    print("完成")


if __name__ == "__main__":
    main()
