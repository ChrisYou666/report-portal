"""
从 ods.sap_stg_zest_blockc 重建 dwd.sap_harvest_actual_block_daily。
由 app/api/index_mgmt.py 的 ODS→DWD 步骤调用。
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

# 读取 .env 里的 DATABASE_URL
env_path = Path(__file__).parent.parent / ".env"
PG_DSN = "postgresql://portal:portal@127.0.0.1:5432/report_portal"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL=") or line.startswith("database_url="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            # 把 SQLAlchemy URL 转成 psycopg DSN
            PG_DSN = raw.replace("postgresql+psycopg://", "postgresql://")
            break


def rebuild(pg: psycopg.Connection) -> int:
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


def main() -> None:
    print(f"连接 PostgreSQL…")
    pg = psycopg.connect(PG_DSN)
    try:
        n = rebuild(pg)
        print(f"Built dwd.sap_harvest_actual_block_daily: {n} rows")
    finally:
        pg.close()


if __name__ == "__main__":
    main()
