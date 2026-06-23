from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

from build_sap_dimensions import build_sap_dimensions


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
TARGET_SCHEMA = "dwd"
TARGET_TABLE = "sap_harvest_actual_block_daily"


def main() -> None:
    args = parse_args()
    env = load_env(DEFAULT_ENV_PATH)
    dsn = normalize_postgres_dsn(get_config("DATABASE_URL", env, required=True))

    with psycopg.connect(dsn) as conn:
        build_table(conn)
        print_summary(conn, args.limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build DWD daily block-level SAP harvest actual production from ODS."
    )
    parser.add_argument("--limit", type=int, default=20, help="Rows to print after refresh.")
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
        raise RuntimeError(f"Missing config: {name}")
    return value


def normalize_postgres_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://", 1)


def build_table(conn: psycopg.Connection) -> None:
    build_sap_dimensions(conn)

    sql = f"""
    create schema if not exists {TARGET_SCHEMA};

    drop table if exists {TARGET_SCHEMA}.{TARGET_TABLE};

    create table {TARGET_SCHEMA}.{TARGET_TABLE} (
        date date not null,
        estate_code varchar(40) not null,
        estate_name varchar(120),
        division_code varchar(40),
        division_name varchar(120),
        block_code varchar(80) not null,
        block_name varchar(120),
        production_bg numeric(18, 4) not null,
        production_ag numeric(18, 4) not null,
        unit varchar(20) not null default 'kg',
        source_system varchar(80) not null default 'SAP',
        source_table varchar(120) not null default 'ods.sap_stg_zest_blockc',
        source_row_count integer not null default 0,
        quality_status varchar(40) not null default 'ok',
        quality_message text,
        built_at timestamptz not null default now(),
        constraint uq_sap_harvest_actual_block_daily
            unique (date, estate_code, division_code, block_code)
    );

    insert into {TARGET_SCHEMA}.{TARGET_TABLE} (
        date,
        estate_code,
        estate_name,
        division_code,
        division_name,
        block_code,
        block_name,
        production_bg,
        production_ag,
        unit,
        source_system,
        source_table,
        source_row_count,
        quality_status,
        quality_message,
        built_at
    )
    with block_dim as (
        select
            bukrs,
            estnr,
            divnr,
            block,
            bname as block_name,
            nullif(kdatb, '')::date as valid_from,
            nullif(kdate, '')::date as valid_to
        from ods.sap_stg_zest_block
        where nullif(kdatb, '') is not null
          and nullif(kdate, '') is not null
    ),
    division_dim as (
        select
            bukrs,
            estnr,
            divnr,
            name1 as division_name,
            nullif(kdatb, '')::date as valid_from,
            nullif(kdate, '')::date as valid_to
        from ods.sap_stg_zest_division
        where nullif(kdatb, '') is not null
          and nullif(kdate, '') is not null
    ),
    estate_dim as (
        select
            estate_code,
            max(estate_name) as estate_name,
            max(estate_name_mand) as estate_name_mand,
            max(estate_master_name) as estate_master_name
        from dim.sap_estate
        group by estate_code
    ),
    source_rows as (
        select
            g.crdat::date as date,
            g.bukrs,
            g.estnr,
            g.block,
            g.ntqty,
            g.srqty
        from ods.sap_stg_zest_blockc g
        where g.crdat ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
    )
    select
        s.date,
        s.estnr as estate_code,
        coalesce(max(e.estate_name), max(e.estate_name_mand), max(e.estate_master_name), '') as estate_name,
        coalesce(d.divnr, '') as division_code,
        coalesce(max(v.division_name), '') as division_name,
        s.block as block_code,
        coalesce(max(d.block_name), '') as block_name,
        sum(coalesce(nullif(s.ntqty, '')::numeric, 0) - coalesce(nullif(s.srqty, '')::numeric, 0)) as production_bg,
        sum(coalesce(nullif(s.ntqty, '')::numeric, 0)) as production_ag,
        'kg'::varchar(20) as unit,
        'SAP'::varchar(80) as source_system,
        'ods.sap_stg_zest_blockc'::varchar(120) as source_table,
        count(*)::integer as source_row_count,
        'ok'::varchar(40) as quality_status,
        null::text as quality_message,
        now() as built_at
    from source_rows s
    left join lateral (
        select bd.*
        from block_dim bd
        where bd.bukrs = s.bukrs
          and bd.estnr = s.estnr
          and bd.block = s.block
          and s.date between bd.valid_from and bd.valid_to
        order by bd.valid_from desc, bd.valid_to desc
        limit 1
    ) d on true
    left join lateral (
        select vd.*
        from division_dim vd
        where vd.bukrs = s.bukrs
          and vd.estnr = s.estnr
          and vd.divnr = d.divnr
          and s.date between vd.valid_from and vd.valid_to
        order by vd.valid_from desc, vd.valid_to desc
        limit 1
    ) v on true
    left join estate_dim e
      on e.estate_code = s.estnr
    group by
        s.date,
        s.estnr,
        d.divnr,
        s.block;

    create index idx_sap_harvest_actual_date
        on {TARGET_SCHEMA}.{TARGET_TABLE} (date);
    create index idx_sap_harvest_actual_estate_date
        on {TARGET_SCHEMA}.{TARGET_TABLE} (estate_code, date);
    create index idx_sap_harvest_actual_division_date
        on {TARGET_SCHEMA}.{TARGET_TABLE} (estate_code, division_code, date);
    create index idx_sap_harvest_actual_block_date
        on {TARGET_SCHEMA}.{TARGET_TABLE} (estate_code, division_code, block_code, date);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def print_summary(conn: psycopg.Connection, limit: int) -> None:
    with conn.cursor() as cur:
        cur.execute(f"select count(*), min(date), max(date) from {TARGET_SCHEMA}.{TARGET_TABLE}")
        total_rows, min_date, max_date = cur.fetchone()
        print(f"Built {TARGET_SCHEMA}.{TARGET_TABLE}: {total_rows} rows", flush=True)
        print(f"Date range: {min_date} to {max_date}", flush=True)

        cur.execute(
            f"""
            select
                count(*) filter (where production_ag > production_bg),
                count(*) filter (where production_ag < production_bg),
                count(*) filter (where production_ag = production_bg)
            from {TARGET_SCHEMA}.{TARGET_TABLE}
            """
        )
        after_gt_before, after_lt_before, after_eq_before = cur.fetchone()
        print(
            "Production compare: "
            f"AG>BG {after_gt_before}; AG<BG {after_lt_before}; AG=BG {after_eq_before}"
        , flush=True)

        cur.execute(
            f"""
            select
                date,
                estate_code,
                estate_name,
                division_code,
                division_name,
                block_code,
                block_name,
                production_bg,
                production_ag,
                unit,
                source_row_count
            from {TARGET_SCHEMA}.{TARGET_TABLE}
            order by date desc, estate_code, division_code, block_code
            limit %s
            """,
            (limit,),
        )
        print(
            "date,estate_code,estate_name,division_code,division_name,block_code,"
            "block_name,production_bg,production_ag,unit,source_row_count"
        , flush=True)
        for row in cur.fetchall():
            print(",".join("" if value is None else str(value) for value in row), flush=True)


if __name__ == "__main__":
    main()
