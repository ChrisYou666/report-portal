from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "backend" / ".env"
DIM_SCHEMA = "dim"


def main() -> None:
    args = parse_args()
    env = load_env(DEFAULT_ENV_PATH)
    dsn = normalize_postgres_dsn(get_config("DATABASE_URL", env, required=True))

    with psycopg.connect(dsn) as conn:
        build_sap_dimensions(conn)
        print_summary(conn, args.limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SAP dimension tables from ODS snapshots.")
    parser.add_argument("--limit", type=int, default=50, help="Rows to print after refresh.")
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


def build_sap_dimensions(conn: psycopg.Connection) -> None:
    sql = f"""
    create schema if not exists {DIM_SCHEMA};

    drop table if exists {DIM_SCHEMA}.sap_estate;

    create table {DIM_SCHEMA}.sap_estate as
    select distinct
        a.bukrs as company_code,
        coalesce(t.butxt, '') as company_name,
        coalesce(company_mand.ddtext, '') as company_name_mand,
        reg.rgnnr as region_code,
        coalesce(reg.name1, '') as region_name,
        coalesce(region_mand.ddtext, '') as region_name_mand,
        b.estnr as estate_code,
        a.prfnr as estate_name,
        coalesce(estate_mand.ddtext, '') as estate_name_mand,
        coalesce(b.name1, '') as estate_master_name,
        a.werks as profile_werks,
        b.werks as estate_werks,
        a.estnr as profile_estnr,
        nullif(a.kdatb, '')::date as profile_valid_from,
        nullif(a.kdate, '')::date as profile_valid_to,
        nullif(b.kdatb, '')::date as estate_valid_from,
        nullif(b.kdate, '')::date as estate_valid_to,
        case
            when b.estnr is null then 'profile_without_estate_master'
            when b.estnr between '21' and '29' then 'estate'
            when b.estnr between '31' and '39' then 'mill'
            when b.estnr between '91' and '99' then 'plasma'
            else 'other'
        end as estate_type,
        now() as built_at
    from ods.sap_stg_zpay_profile a
    left join ods.sap_stg_t001 t
      on a.bukrs = t.bukrs
    left join ods.sap_stg_zest_estate b
      on a.bukrs = b.bukrs
     and right(trim(a.werks), 2) = b.estnr
    left join ods.sap_stg_zest_region reg
      on b.rgnnr = reg.rgnnr
    left join ods.sap_stg_dd07t company_mand
      on a.bukrs = company_mand.domvalue_l
     and trim(company_mand.domname) = 'ZDMCOMPANY'
    left join ods.sap_stg_dd07t estate_mand
      on b.werks = estate_mand.domvalue_l
     and trim(estate_mand.domname) = 'ZDMESTATE'
    left join ods.sap_stg_dd07t region_mand
      on reg.rgnnr = region_mand.domvalue_l
     and trim(region_mand.domname) = 'ZDMREGION';

    create index on {DIM_SCHEMA}.sap_estate (company_code, estate_code);
    create index on {DIM_SCHEMA}.sap_estate (profile_werks);
    create index on {DIM_SCHEMA}.sap_estate (estate_name);
    create index on {DIM_SCHEMA}.sap_estate (estate_name_mand);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def print_summary(conn: psycopg.Connection, limit: int) -> None:
    with conn.cursor() as cur:
        cur.execute(f"select count(*) from {DIM_SCHEMA}.sap_estate")
        print(f"Built {DIM_SCHEMA}.sap_estate: {cur.fetchone()[0]} rows")
        cur.execute(
            f"""
            select
                company_code,
                company_name,
                region_code,
                region_name,
                region_name_mand,
                estate_code,
                estate_name,
                estate_name_mand,
                estate_master_name,
                profile_werks,
                estate_type
            from {DIM_SCHEMA}.sap_estate
            order by company_code, estate_code, estate_name
            limit %s
            """,
            (limit,),
        )
        print(
            "company_code,company_name,region_code,region_name,region_name_mand,"
            "estate_code,estate_name,estate_name_mand,estate_master_name,profile_werks,estate_type"
        )
        for row in cur.fetchall():
            print(",".join("" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
