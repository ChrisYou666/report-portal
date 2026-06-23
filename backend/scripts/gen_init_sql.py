"""生成 init_dwd_schema.sql，包含当前 DWD 所有数据。"""
import psycopg
import datetime
from pathlib import Path

PG_DSN = "postgresql://portal:portal@127.0.0.1:5432/report_portal"
OUT    = Path(__file__).parent / "init_dwd_schema.sql"

DDL_ZPAY = """CREATE TABLE IF NOT EXISTS ods.sap_stg_zpay_profile (
    _ods_loaded_at varchar(30), _source_table varchar(60), _row_hash varchar(64),
    mandt varchar(10), prfnr varchar(40), bukrs varchar(10), kdatb varchar(20),
    kdate varchar(20), prfck varchar(10), estnr varchar(20), werks varchar(20),
    waerk varchar(10), kunnr varchar(20), oer varchar(10), incr varchar(10),
    instf varchar(10), zlock varchar(10), komtp varchar(10), hktyp varchar(10),
    epfnr varchar(20), socso varchar(10), cytyp varchar(10), perib varchar(10),
    npwpn varchar(40), actreg varchar(40), ernam varchar(40), erdat varchar(20),
    erzet varchar(20), aenam varchar(40), aedat varchar(20), aezet varchar(20),
    last_upddate varchar(20)
);"""

DDL_T001 = """CREATE TABLE IF NOT EXISTS ods.sap_stg_t001 (
    _ods_loaded_at varchar(30), _source_table varchar(60), _row_hash varchar(64),
    mandt varchar(10), bukrs varchar(10), butxt varchar(120), ort01 varchar(40),
    land1 varchar(10), waers varchar(10), spras varchar(10), ktopl varchar(10),
    waabw varchar(10), periv varchar(10), kokfi varchar(10), rcomp varchar(10),
    adrnr varchar(20), stceg varchar(40), fikrs varchar(10), xfmco varchar(10),
    xfmcb varchar(10), xfmca varchar(10), txjcd varchar(20), fmhrdate varchar(20),
    buvar varchar(10), fdbuk varchar(10), xfdis varchar(10), xvalv varchar(10),
    xskfn varchar(10), kkber varchar(10), xmwsn varchar(10), mregl varchar(10),
    xgsbe varchar(10), xgjrv varchar(10), xkdft varchar(10), xprod varchar(10),
    xeink varchar(10), xjvaa varchar(10), xvvwa varchar(10), xslta varchar(10),
    xfdmm varchar(10), xfdsd varchar(10), xextb varchar(10), ebukr varchar(10),
    ktop2 varchar(10), umkrs varchar(10), bukrs_glob varchar(10), fstva varchar(10),
    opvar varchar(10), xcovr varchar(10), txkrs varchar(10), wfvar varchar(10),
    xbbbf varchar(10), xbbbe varchar(10), xbbba varchar(10), xbbko varchar(10),
    xstdt varchar(10), mwskv varchar(10), mwska varchar(10), impda varchar(20),
    xnegp varchar(10), xkkbi varchar(10), wt_newwt varchar(10), pp_pdate varchar(20),
    infmt varchar(10), fstvare varchar(10), kopim varchar(10), dkweg varchar(10),
    offsacct varchar(10), bapovar varchar(10), xcos varchar(10), xcession varchar(10),
    xsplt varchar(10), surccm varchar(10), dtprov varchar(10), dtamtc varchar(10),
    dttaxc varchar(10), dttdsp varchar(10), dtaxr varchar(10), xvatdate varchar(10),
    pst_per_var varchar(10), xbbsc varchar(10), fm_derive_acc varchar(10),
    last_upddate varchar(20)
);"""

DDL_ESTATE = """CREATE TABLE IF NOT EXISTS ods.sap_stg_zest_estate (
    _ods_loaded_at varchar(30), _source_table varchar(60), _row_hash varchar(64),
    mandt varchar(10), bukrs varchar(10), estnr varchar(20), kdatb varchar(20),
    kdate varchar(20), rgnnr varchar(20), name1 varchar(120), adrnr varchar(20),
    adrnr2 varchar(20), adrnr3 varchar(20), ort01 varchar(40), land1 varchar(10),
    cont1 varchar(40), tel_number varchar(40), fax_number varchar(40),
    pstlz varchar(20), loekz varchar(10), ernam varchar(40), erdat varchar(20),
    erzet varchar(20), aenam varchar(40), aedat varchar(20), aezet varchar(20),
    estate varchar(40), werks varchar(20), lgort varchar(10), lgort2 varchar(10),
    lgort3 varchar(10), lgort4 varchar(10), zldat varchar(20), menam varchar(40),
    medat varchar(20), mezet varchar(20), amnam varchar(40), amdat varchar(20),
    amzet varchar(20), pro01 varchar(40), last_upddate varchar(20)
);"""

DDL_ODS = """CREATE TABLE IF NOT EXISTS ods.sap_stg_zest_blockc (
    id             bigserial    PRIMARY KEY,
    mandt          varchar(10)  NOT NULL DEFAULT '',
    bukrs          varchar(10)  NOT NULL DEFAULT '',
    estnr          varchar(20)  NOT NULL DEFAULT '',
    werks          varchar(20)  NOT NULL DEFAULT '',
    block          varchar(40)  NOT NULL DEFAULT '',
    crdat          varchar(20)  NOT NULL DEFAULT '',
    qreal          varchar(30)  NOT NULL DEFAULT '',
    ntqty          varchar(30)  NOT NULL DEFAULT '',
    meins          varchar(10)  NOT NULL DEFAULT '',
    _ods_loaded_at varchar(30)  NOT NULL DEFAULT '',
    _source_table  varchar(60)  NOT NULL DEFAULT '',
    _row_hash      varchar(64)  NOT NULL DEFAULT ''
);"""

DDL_DWD = """CREATE TABLE IF NOT EXISTS dwd.sap_harvest_actual_block_daily (
    date             date          NOT NULL,
    estate_code      varchar(20)   NOT NULL,
    estate_name      varchar(120)  NOT NULL DEFAULT '',
    division_code    varchar(40)   NOT NULL DEFAULT '',
    division_name    varchar(120)  NOT NULL DEFAULT '',
    block_code       varchar(40)   NOT NULL DEFAULT '',
    block_name       varchar(120)  NOT NULL DEFAULT '',
    production_bg    double precision       DEFAULT 0,
    production_ag    double precision       DEFAULT 0,
    unit             varchar(20)   NOT NULL DEFAULT 'kg',
    source_system    varchar(40)   NOT NULL DEFAULT 'SAP',
    source_table     varchar(120)  NOT NULL DEFAULT '',
    source_row_count integer       NOT NULL DEFAULT 0,
    quality_status   varchar(20)   NOT NULL DEFAULT 'ok',
    built_at         timestamp     NOT NULL DEFAULT now()
);"""

COLS = ("date", "estate_code", "estate_name", "division_code", "division_name",
        "block_code", "block_name", "production_bg", "production_ag",
        "unit", "source_system", "source_table", "source_row_count",
        "quality_status", "built_at")

BATCH = 500


def esc(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return f"'{v}'"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def main():
    conn = psycopg.connect(PG_DSN)
    cur  = conn.cursor()

    lines = [
        "-- ============================================================",
        "-- DWD / ODS Schema 初始化脚本（含农业产量及主数据）",
        "-- 运行：psql -U portal -d report_portal -f scripts/init_dwd_schema.sql",
        "-- ============================================================",
        "\\set ON_ERROR_STOP off",
        "",
        "-- 1. 创建 Schema",
        "CREATE SCHEMA IF NOT EXISTS ods;",
        "CREATE SCHEMA IF NOT EXISTS dwd;",
        "",
        "-- 2. ODS 主数据表",
        DDL_ZPAY,
        DDL_T001,
        DDL_ESTATE,
        "",
        "-- 3. ODS 原始层（blockc）",
        DDL_ODS,
        "CREATE INDEX IF NOT EXISTS idx_ods_blockc_crdat  ON ods.sap_stg_zest_blockc(crdat);",
        "CREATE INDEX IF NOT EXISTS idx_ods_blockc_estnr  ON ods.sap_stg_zest_blockc(estnr);",
        "",
        "-- 4. DWD 日度产量宽表",
        DDL_DWD,
        "CREATE INDEX IF NOT EXISTS idx_dwd_harvest_date   ON dwd.sap_harvest_actual_block_daily(date);",
        "CREATE INDEX IF NOT EXISTS idx_dwd_harvest_estate ON dwd.sap_harvest_actual_block_daily(estate_code);",
        "",
        "-- 5. 写入主数据",
    ]

    # 导出三张小表
    for tbl, ddl_comment in [
        ("sap_stg_zpay_profile",  "zpay_profile"),
        ("sap_stg_t001",          "t001"),
        ("sap_stg_zest_estate",   "zest_estate"),
    ]:
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='ods' AND table_name=%s ORDER BY ordinal_position", (tbl,))
        cols_list = [r[0] for r in cur.fetchall()]
        col_str = ", ".join(cols_list)
        cur.execute(f"SELECT {col_str} FROM ods.{tbl}")
        rows = cur.fetchall()
        if rows:
            prefix = f"INSERT INTO ods.{tbl} ({col_str}) VALUES"
            values = ",\n".join("  (" + ", ".join(esc(v) for v in row) + ")" for row in rows)
            lines.append(f"TRUNCATE TABLE ods.{tbl};")
            lines.append(prefix)
            lines.append(values + ";")
            lines.append(f"-- {tbl}: {len(rows)} rows")
            lines.append("")

    lines += [
        "-- 6. 写入 DWD 产量数据",
        "TRUNCATE TABLE dwd.sap_harvest_actual_block_daily;",
        "",
    ]

    col_list = ", ".join(COLS)
    insert_prefix = f"INSERT INTO dwd.sap_harvest_actual_block_daily ({col_list}) VALUES"

    cur.execute(f"""
        SELECT {col_list}
        FROM dwd.sap_harvest_actual_block_daily
        ORDER BY date, estate_code, block_code
    """)

    total = 0
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        values = ",\n".join("  (" + ", ".join(esc(v) for v in row) + ")" for row in rows)
        lines.append(insert_prefix)
        lines.append(values + ";")
        lines.append("")
        total += len(rows)
        if total % 50000 == 0:
            print(f"  {total:,} 行...")

    lines += [
        "-- 验证",
        "SELECT count(*), min(date), max(date) FROM dwd.sap_harvest_actual_block_daily;",
        "SELECT 'ods.sap_stg_zpay_profile' AS tbl, count(*) FROM ods.sap_stg_zpay_profile",
        "UNION ALL SELECT 'ods.sap_stg_t001', count(*) FROM ods.sap_stg_t001",
        "UNION ALL SELECT 'ods.sap_stg_zest_estate', count(*) FROM ods.sap_stg_zest_estate;",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    conn.close()
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"完成：{total:,} 行，文件大小 {size_mb:.1f} MB → {OUT}")


if __name__ == "__main__":
    main()
