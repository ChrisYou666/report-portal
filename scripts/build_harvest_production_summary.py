from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

from build_harvest_dwd import build_dwd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
TARGET_SCHEMA = "dws"
TARGET_TABLE = "harvest_production_daily_summary"


def main() -> None:
    args = parse_args()
    env = load_env(DEFAULT_ENV_PATH)
    dsn = normalize_postgres_dsn(get_config("DATABASE_URL", env, required=True))

    with psycopg.connect(dsn) as conn:
        if not args.skip_dwd:
            build_dwd(conn)
        build_summary(conn)
        print_summary(conn, args.limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DWS harvest production monitoring summary from DWD tables.")
    parser.add_argument("--limit", type=int, default=20, help="Rows to print after refresh.")
    parser.add_argument("--skip-dwd", action="store_true", help="Do not rebuild DWD before DWS.")
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


def build_summary(conn: psycopg.Connection) -> None:
    sql = f"""
    create schema if not exists {TARGET_SCHEMA};

    drop table if exists {TARGET_SCHEMA}.{TARGET_TABLE};

    create table {TARGET_SCHEMA}.{TARGET_TABLE} as
    with site_company_mapping as (
        select * from (values
            (convert_from(decode('e4b883e59bad', 'hex'), 'UTF8'), 'AS'::text)
        ) as mapping(report_site_name, company_code)
    ),
    report_akp_division_daily as (
        select
            report_date,
            period_month,
            site_name as report_site_name,
            division_code,
            sum(sample_area_ha) as akp_sample_area_ha,
            sum(sample_harvest_count) as akp_sample_harvest_count,
            case
                when nullif(sum(sample_area_ha), 0) is null then avg(akp_density_percent)
                else sum(akp_density_percent * sample_area_ha) / sum(sample_area_ha)
            end as akp_density_percent,
            sum(akp_estimated_harvest_area_ha) as akp_estimated_harvest_area_ha,
            sum(akp_estimated_production_kg) as akp_estimated_production_kg,
            sum(akp_estimated_bunch_count) as akp_estimated_bunch_count,
            count(*) as akp_source_rows
        from dwd.report_akp_density_block_daily
        group by report_date, period_month, site_name, division_code
    ),
    report_bbc_division_daily as (
        select
            report_date,
            period_month,
            site_name as report_site_name,
            division_code,
            sum(luas_ha) as report_luas_ha,
            sum(bbc_target_kg) as report_bbc_target_kg,
            sum(report_actual_today_kg) as report_actual_today_kg,
            sum(report_actual_to_date_kg) as report_actual_to_date_kg,
            sum(daily_target_kg) as report_daily_target_kg,
            count(*) as production_monitoring_source_rows
        from dwd.report_production_monitoring_division_daily
        group by report_date, period_month, site_name, division_code
    ),
    report_budget_division_monthly as (
        select
            report_date,
            period_month,
            site_name as report_site_name,
            division_code,
            sum(mature_area_ha) as report_budget_mature_area_ha,
            sum(monthly_budget_production_kg) as report_monthly_budget_production_kg,
            count(*) as production_budget_source_rows
        from dwd.report_production_budget_division_monthly
        group by report_date, period_month, site_name, division_code
    ),
    report_estimate_division_daily as (
        select
            report_date,
            period_month,
            site_name as report_site_name,
            division_code,
            sum(mature_area_ha) as report_estimate_mature_area_ha,
            sum(estimated_harvest_area_ha) as report_estimated_harvest_area_ha,
            sum(estimated_production_kg) as report_estimated_production_kg,
            case
                when nullif(sum(mature_area_ha), 0) is null then avg(akp_percent)
                else sum(akp_percent * mature_area_ha) / sum(mature_area_ha)
            end as report_estimate_akp_percent,
            count(*) as production_estimate_source_rows
        from dwd.report_production_estimate_division_daily
        group by report_date, period_month, site_name, division_code
    ),
    report_division_keys as (
        select report_date, period_month, report_site_name, division_code
        from report_akp_division_daily
        union
        select report_date, period_month, report_site_name, division_code
        from report_bbc_division_daily
        union
        select report_date, period_month, report_site_name, division_code
        from report_budget_division_monthly
        union
        select report_date, period_month, report_site_name, division_code
        from report_estimate_division_daily
    ),
    enriched as (
        select
            keys.report_date,
            keys.period_month,
            map.company_code,
            null::text as estate_code,
            null::text as estate_name,
            keys.report_site_name,
            keys.division_code,
            null::text as division_name,
            null::text as report_block_code,
            null::text as sap_block_code,
            coalesce(report_bbc.report_luas_ha, report_budget.report_budget_mature_area_ha, report_estimate.report_estimate_mature_area_ha) as mature_area_ha,
            report_bbc.report_bbc_target_kg as monthly_bbc_target_kg,
            report_budget.report_monthly_budget_production_kg as monthly_budget_production_kg,
            akp.akp_sample_area_ha,
            akp.akp_sample_harvest_count,
            coalesce(akp.akp_density_percent, report_estimate.report_estimate_akp_percent) as akp_density_percent,
            coalesce(akp.akp_estimated_harvest_area_ha, report_estimate.report_estimated_harvest_area_ha) as akp_estimated_harvest_area_ha,
            coalesce(akp.akp_estimated_production_kg, report_estimate.report_estimated_production_kg) as akp_estimated_production_kg,
            akp.akp_estimated_bunch_count,
            akp.akp_source_rows,
            report_bbc.production_monitoring_source_rows,
            report_budget.production_budget_source_rows,
            report_estimate.production_estimate_source_rows,
            report_bbc.report_actual_today_kg as daily_actual_production_kg,
            report_bbc.report_actual_to_date_kg as month_to_date_actual_production_kg,
            (report_bbc.production_monitoring_source_rows is not null) as actual_from_production_monitoring
        from report_division_keys keys
        join site_company_mapping map
          on map.report_site_name = keys.report_site_name
        left join report_akp_division_daily akp
          on akp.report_date = keys.report_date
         and akp.report_site_name = keys.report_site_name
         and akp.division_code = keys.division_code
        left join report_bbc_division_daily report_bbc
          on report_bbc.report_date = keys.report_date
         and report_bbc.report_site_name = keys.report_site_name
         and report_bbc.division_code = keys.division_code
        left join report_budget_division_monthly report_budget
          on report_budget.period_month = keys.period_month
         and report_budget.report_site_name = keys.report_site_name
         and report_budget.division_code = keys.division_code
        left join report_estimate_division_daily report_estimate
          on report_estimate.report_date = keys.report_date
         and report_estimate.report_site_name = keys.report_site_name
         and report_estimate.division_code = keys.division_code
    )
    select
        report_date,
        period_month,
        company_code,
        estate_code,
        estate_name,
        report_site_name,
        division_code,
        division_name,
        report_block_code,
        sap_block_code,
        mature_area_ha,
        monthly_bbc_target_kg as bbc_estimated_production_kg,
        akp_density_percent,
        akp_estimated_harvest_area_ha,
        akp_estimated_production_kg,
        daily_actual_production_kg,
        case
            when nullif(akp_estimated_production_kg, 0) is null then null
            else daily_actual_production_kg / akp_estimated_production_kg
        end as daily_production_completion_rate,
        month_to_date_actual_production_kg,
        monthly_bbc_target_kg,
        case
            when nullif(monthly_bbc_target_kg, 0) is null then null
            else month_to_date_actual_production_kg / monthly_bbc_target_kg
        end as bbc_target_completion_rate,
        case
            when nullif(monthly_bbc_target_kg, 0) is null then null
            else monthly_bbc_target_kg - month_to_date_actual_production_kg
        end as bbc_remaining_target_kg,
        monthly_budget_production_kg,
        case
            when nullif(monthly_budget_production_kg, 0) is null then null
            else month_to_date_actual_production_kg / monthly_budget_production_kg
        end as budget_completion_rate,
        case
            when nullif(monthly_budget_production_kg, 0) is null then null
            else monthly_budget_production_kg - month_to_date_actual_production_kg
        end as budget_remaining_target_kg,
        ((date_trunc('month', report_date)::date + interval '1 month - 1 day')::date - report_date) as month_remaining_days,
        akp_source_rows,
        production_monitoring_source_rows,
        production_budget_source_rows,
        production_estimate_source_rows,
        actual_from_production_monitoring,
        concat_ws('; ',
            case when company_code is null then 'SAP company mapping missing for report site' end,
            case when daily_actual_production_kg is null then 'missing uploaded production monitoring actual production' end,
            case when mature_area_ha is null then 'missing uploaded mature area' end,
            case when mature_area_ha = 0 then 'zero uploaded mature area' end,
            case when monthly_bbc_target_kg is null then 'missing uploaded BBC target' end,
            case when monthly_bbc_target_kg = 0 then 'zero uploaded BBC target' end,
            case when production_monitoring_source_rows is not null then 'BBC target from uploaded production monitoring report' end,
            case when monthly_budget_production_kg is null then 'missing monthly budget target' end,
            case when monthly_budget_production_kg = 0 then 'zero monthly budget target' end,
            case when production_budget_source_rows is not null then 'budget target from uploaded production budget report' end,
            case when production_estimate_source_rows is not null and akp_source_rows is null then 'AKP estimated production from uploaded estimate report' end,
            case when akp_estimated_production_kg is null then 'missing report AKP estimated production' end
        ) as data_note,
        now() as built_at
    from enriched;

    create index on {TARGET_SCHEMA}.{TARGET_TABLE} (report_date);
    create index on {TARGET_SCHEMA}.{TARGET_TABLE} (period_month, company_code, division_code);
    create index on {TARGET_SCHEMA}.{TARGET_TABLE} (report_date, report_site_name, division_code);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def print_summary(conn: psycopg.Connection, limit: int) -> None:
    with conn.cursor() as cur:
        cur.execute(f"select count(*) from {TARGET_SCHEMA}.{TARGET_TABLE}")
        total_rows = cur.fetchone()[0]
        cur.execute(
            f"""
            select
                min(report_date),
                max(report_date),
                count(*) filter (where daily_actual_production_kg is not null),
                count(*) filter (where akp_estimated_production_kg is not null)
            from {TARGET_SCHEMA}.{TARGET_TABLE}
            """
        )
        min_date, max_date, uploaded_actual_rows, akp_rows = cur.fetchone()
        print(f"Built {TARGET_SCHEMA}.{TARGET_TABLE}: {total_rows} rows")
        print(f"Date range: {min_date} to {max_date}")
        print(f"Uploaded actual rows: {uploaded_actual_rows}; AKP report rows: {akp_rows}")

        cur.execute(
            f"""
            select
                report_date,
                coalesce(estate_name, report_site_name, '') as estate_or_site,
                division_code,
                round(daily_actual_production_kg::numeric, 2),
                round(akp_estimated_production_kg::numeric, 2),
                round((daily_production_completion_rate * 100)::numeric, 2),
                round(month_to_date_actual_production_kg::numeric, 2),
                round(monthly_bbc_target_kg::numeric, 2),
                round(monthly_budget_production_kg::numeric, 2),
                data_note
            from {TARGET_SCHEMA}.{TARGET_TABLE}
            order by report_date desc, estate_or_site, division_code
            limit %s
            """,
            (limit,),
        )
        print(
            "report_date,estate_or_site,division_code,daily_actual_kg,akp_estimated_kg,"
            "daily_completion_pct,mtd_actual_kg,bbc_target_kg,budget_kg,data_note"
        )
        for row in cur.fetchall():
            print(",".join("" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
