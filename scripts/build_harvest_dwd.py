from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

from build_sap_dimensions import build_sap_dimensions


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
DWD_SCHEMA = "dwd"


def main() -> None:
    args = parse_args()
    env = load_env(DEFAULT_ENV_PATH)
    dsn = normalize_postgres_dsn(get_config("DATABASE_URL", env, required=True))

    with psycopg.connect(dsn) as conn:
        build_dwd(conn)
        print_summary(conn, args.limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DWD harvest facts from SAP ODS and report parsed data.")
    parser.add_argument("--limit", type=int, default=10, help="Rows to print for each DWD table.")
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


def build_dwd(conn: psycopg.Connection) -> None:
    build_sap_dimensions(conn)
    sql = f"""
    create schema if not exists {DWD_SCHEMA};

    drop table if exists {DWD_SCHEMA}.sap_harvest_actual_block_daily;
    drop table if exists {DWD_SCHEMA}.sap_harvest_target_block_monthly;
    drop table if exists {DWD_SCHEMA}.report_akp_density_block_daily;
    drop table if exists {DWD_SCHEMA}.report_production_monitoring_division_daily;
    drop table if exists {DWD_SCHEMA}.report_production_budget_division_monthly;
    drop table if exists {DWD_SCHEMA}.report_production_estimate_division_daily;

    create table {DWD_SCHEMA}.sap_harvest_actual_block_daily as
    with block_dim as (
        select
            bukrs,
            estnr,
            divnr,
            block,
            bname as block_name,
            nullif(kdatb, '')::date as valid_from,
            nullif(kdate, '')::date as valid_to,
            seedo,
            yplan
        from ods.sap_stg_zest_block
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
    ),
    estate_dim as (
        select
            company_code,
            estate_code,
            max(estate_name) as estate_name,
            max(estate_name_mand) as estate_name_mand,
            max(estate_master_name) as estate_master_name
        from dim.sap_estate
        group by company_code, estate_code
    )
    select
        g.crdat::date as report_date,
        to_char(g.crdat::date, 'YYYYMM') as period_month,
        g.bukrs as company_code,
        g.estnr as estate_code,
        coalesce(e.estate_name, '') as estate_name,
        coalesce(e.estate_name_mand, '') as estate_name_mand,
        coalesce(e.estate_master_name, '') as estate_master_name,
        d.divnr as division_code,
        coalesce(v.division_name, '') as division_name,
        g.block as block_code,
        d.block_name,
        d.seedo as seed_code,
        d.yplan as planting_year,
        sum(coalesce(nullif(g.ntqty, '')::numeric, 0) - coalesce(nullif(g.srqty, '')::numeric, 0)) as actual_production_kg,
        'KG'::text as production_unit,
        'SAP:STG_ZEST_BLOCKC'::text as source_system,
        now() as built_at
    from ods.sap_stg_zest_blockc g
    join block_dim d
      on d.bukrs = g.bukrs
     and d.estnr = g.estnr
     and d.block = g.block
     and g.crdat::date between d.valid_from and d.valid_to
    left join estate_dim e
      on e.company_code = g.bukrs
     and e.estate_code = g.estnr
    left join division_dim v
      on v.bukrs = g.bukrs
     and v.estnr = g.estnr
     and v.divnr = d.divnr
     and g.crdat::date between v.valid_from and v.valid_to
    where g.crdat ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
    group by
        g.crdat::date,
        to_char(g.crdat::date, 'YYYYMM'),
        g.bukrs,
        g.estnr,
        e.estate_name,
        e.estate_name_mand,
        e.estate_master_name,
        d.divnr,
        v.division_name,
        g.block,
        d.block_name,
        d.seedo,
        d.yplan;

    create table {DWD_SCHEMA}.sap_harvest_target_block_monthly as
    with block_dim as (
        select
            bukrs,
            estnr,
            divnr,
            block,
            bname as block_name,
            nullif(kdatb, '')::date as valid_from,
            nullif(kdate, '')::date as valid_to,
            seedo,
            yplan
        from ods.sap_stg_zest_block
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
    ),
    estate_dim as (
        select
            company_code,
            estate_code,
            max(estate_name) as estate_name,
            max(estate_name_mand) as estate_name_mand,
            max(estate_master_name) as estate_master_name
        from dim.sap_estate
        group by company_code, estate_code
    ),
    target_keys as (
        select spmon as period_month, bukrs, estnr, divnr, block
        from ods.sap_stg_zest_blockb
        where spmon ~ '^20\\d{{4}}$'
        union
        select munth as period_month, bukrs, estnr, divnr, block
        from ods.sap_stg_zest_blockp
        where munth ~ '^20\\d{{4}}$'
    ),
    budget_area as (
        select
            spmon as period_month,
            bukrs,
            estnr,
            divnr,
            block,
            sum(coalesce(nullif(hectr, '')::numeric, 0)) as mature_area_ha,
            sum(coalesce(nullif(qbdgt, '')::numeric, 0)) as monthly_budget_production_kg
        from ods.sap_stg_zest_blockb
        where spmon ~ '^20\\d{{4}}$'
        group by spmon, bukrs, estnr, divnr, block
    ),
    bbc as (
        select
            munth as period_month,
            bukrs,
            estnr,
            divnr,
            block,
            sum(coalesce(nullif(qreal, '')::numeric, 0)) as monthly_bbc_target_kg
        from ods.sap_stg_zest_blockp
        where munth ~ '^20\\d{{4}}$'
        group by munth, bukrs, estnr, divnr, block
    )
    select
        k.period_month,
        k.bukrs as company_code,
        k.estnr as estate_code,
        coalesce(e.estate_name, '') as estate_name,
        coalesce(e.estate_name_mand, '') as estate_name_mand,
        coalesce(e.estate_master_name, '') as estate_master_name,
        k.divnr as division_code,
        coalesce(v.division_name, '') as division_name,
        k.block as block_code,
        coalesce(d.block_name, '') as block_name,
        d.seedo as seed_code,
        d.yplan as planting_year,
        coalesce(ba.mature_area_ha, 0) as mature_area_ha,
        ba.monthly_budget_production_kg,
        b.monthly_bbc_target_kg,
        'KG'::text as target_unit,
        'SAP:STG_ZEST_BLOCKB/STG_ZEST_BLOCKP'::text as source_system,
        now() as built_at
    from target_keys k
    left join budget_area ba
      on ba.period_month = k.period_month
     and ba.bukrs = k.bukrs
     and ba.estnr = k.estnr
     and ba.divnr = k.divnr
     and ba.block = k.block
    left join bbc b
      on b.period_month = k.period_month
     and b.bukrs = k.bukrs
     and b.estnr = k.estnr
     and b.divnr = k.divnr
     and b.block = k.block
    left join block_dim d
      on d.bukrs = k.bukrs
     and d.estnr = k.estnr
     and d.divnr = k.divnr
     and d.block = k.block
     and to_date(k.period_month || '01', 'YYYYMMDD') between d.valid_from and d.valid_to
    left join estate_dim e
      on e.company_code = k.bukrs
     and e.estate_code = k.estnr
    left join division_dim v
      on v.bukrs = k.bukrs
     and v.estnr = k.estnr
     and v.divnr = k.divnr
     and to_date(k.period_month || '01', 'YYYYMMDD') between v.valid_from and v.valid_to;

    create table {DWD_SCHEMA}.report_akp_density_block_daily as
    select
        report_date,
        to_char(report_date, 'YYYYMM') as period_month,
        department,
        site as site_name,
        division as division_code,
        blok as block_code,
        sap as sap_block_code,
        luas_ha as sample_area_ha,
        panen_count as sample_harvest_count,
        akp_percent as akp_density_percent,
        case
            when luas_ha is null or akp_percent is null then null
            else luas_ha * akp_percent / 100.0
        end as akp_estimated_harvest_area_ha,
        panen_kg as akp_estimated_production_kg,
        jumlah_janjang as akp_estimated_bunch_count,
        tk_panen as harvester_count,
        batch_no as source_batch_no,
        file_id as source_file_id,
        source_record_id,
        quality_status,
        quality_message,
        'REPORT_UPLOAD:AKP_DENSITY'::text as source_system,
        created_at as source_created_at,
        now() as built_at
    from public.dwd_akp_density_daily
    where row_label = 'detail';

    create table {DWD_SCHEMA}.report_production_monitoring_division_daily as
    select
        report_date,
        to_char(report_date, 'YYYYMM') as period_month,
        department,
        site as site_name,
        division as division_code,
        luas_ha,
        bbc_ton * 1000.0 as bbc_target_kg,
        actual_today_ton * 1000.0 as report_actual_today_kg,
        actual_to_date_ton * 1000.0 as report_actual_to_date_kg,
        actual_vs_bbc_percent,
        remaining_bbc_ton * 1000.0 as remaining_bbc_kg,
        remaining_effective_days,
        daily_target_ton * 1000.0 as daily_target_kg,
        batch_no as source_batch_no,
        file_id as source_file_id,
        source_record_id,
        quality_status,
        quality_message,
        'REPORT_UPLOAD:PRODUCTION_MONITORING'::text as source_system,
        created_at as source_created_at,
        now() as built_at
    from public.dwd_production_monitoring_daily
    where row_label = 'detail';

    create table {DWD_SCHEMA}.report_production_budget_division_monthly as
    select
        report_date,
        to_char(report_date, 'YYYYMM') as period_month,
        department,
        site as site_name,
        division as division_code,
        mature_area_ha,
        case extract(month from report_date)::int
            when 1 then budget_jan_ton
            when 2 then budget_feb_ton
            when 3 then budget_mar_ton
            when 4 then budget_apr_ton
            when 5 then budget_may_ton
            when 6 then budget_jun_ton
            when 7 then budget_jul_ton
            when 8 then budget_aug_ton
            when 9 then budget_sep_ton
            when 10 then budget_oct_ton
            when 11 then budget_nov_ton
            when 12 then budget_dec_ton
        end * 1000.0 as monthly_budget_production_kg,
        annual_budget_ton * 1000.0 as annual_budget_production_kg,
        yield_ton_per_ha,
        batch_no as source_batch_no,
        file_id as source_file_id,
        source_record_id,
        quality_status,
        quality_message,
        'REPORT_UPLOAD:PRODUCTION_BUDGET'::text as source_system,
        created_at as source_created_at,
        now() as built_at
    from public.dwd_production_budget_monthly
    where row_label = 'detail';

    create table {DWD_SCHEMA}.report_production_estimate_division_daily as
    select
        report_date,
        to_char(report_date, 'YYYYMM') as period_month,
        department,
        site as site_name,
        division as division_code,
        mature_area_ha,
        estimated_harvest_area_ha,
        estimated_production_kg,
        akp_percent,
        batch_no as source_batch_no,
        file_id as source_file_id,
        source_record_id,
        quality_status,
        quality_message,
        'REPORT_UPLOAD:PRODUCTION_ESTIMATE'::text as source_system,
        created_at as source_created_at,
        now() as built_at
    from public.dwd_production_estimate_daily
    where row_label = 'detail';

    create index on {DWD_SCHEMA}.sap_harvest_actual_block_daily (report_date, company_code, estate_code, division_code);
    create index on {DWD_SCHEMA}.sap_harvest_target_block_monthly (period_month, company_code, estate_code, division_code);
    create index on {DWD_SCHEMA}.report_akp_density_block_daily (report_date, site_name, division_code);
    create index on {DWD_SCHEMA}.report_production_monitoring_division_daily (report_date, site_name, division_code);
    create index on {DWD_SCHEMA}.report_production_budget_division_monthly (period_month, site_name, division_code);
    create index on {DWD_SCHEMA}.report_production_estimate_division_daily (report_date, site_name, division_code);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def print_summary(conn: psycopg.Connection, limit: int) -> None:
    tables = [
        "sap_harvest_actual_block_daily",
        "sap_harvest_target_block_monthly",
        "report_akp_density_block_daily",
        "report_production_monitoring_division_daily",
        "report_production_budget_division_monthly",
        "report_production_estimate_division_daily",
    ]
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"select count(*) from {DWD_SCHEMA}.{table}")
            count = cur.fetchone()[0]
            print(f"Built {DWD_SCHEMA}.{table}: {count} rows")
            cur.execute(f"select * from {DWD_SCHEMA}.{table} limit %s", (limit,))
            columns = [desc.name for desc in cur.description]
            print(",".join(columns))
            for row in cur.fetchall():
                print(",".join("" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
