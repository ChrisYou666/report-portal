from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app import models

    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    _bootstrap_admin()


def ensure_schema_updates() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "alter table if exists dwd_harvester_attendance_daily "
                "add column if not exists worker_type varchar(80) default ''"
            )
        )
        connection.execute(
            text(
                "alter table if exists dwd_production_monitoring_daily "
                "add column if not exists daily_target_ton double precision"
            )
        )
        connection.execute(
            text(
                "alter table if exists dwd_production_budget_monthly "
                "add column if not exists yield_ton_per_ha double precision"
            )
        )
        # dwd_agri_harvest_rotation_monthly 字段重命名
        for old_col, new_col in [
            ("prev_month_days_since_harvest", "prev_month_days_unharvested"),
            ("current_days_since_harvest",    "current_month_days_unharvested"),
        ]:
            try:
                connection.execute(text(
                    f"alter table if exists dwd_agri_harvest_rotation_monthly "
                    f"rename column {old_col} to {new_col}"
                ))
            except Exception:
                pass
        # dim 层新增列（存量数据库升级）
        for sql in [
            "alter table if exists dim_site add column if not exists company_code varchar(40) not null default ''",
            "alter table if exists dim_division add column if not exists company_code varchar(40) not null default ''",
        ]:
            try:
                connection.execute(text(sql))
            except Exception:
                pass
        for sql in _NULLABLE_FK_SQLS:
            try:
                connection.execute(text(sql))
            except Exception:
                pass
        for sql in _UNIQUE_INDEX_SQLS:
            try:
                connection.execute(text(sql))
            except Exception:
                pass

    # 独立事务：新增列，避免被上方事务中断影响
    for _sql in [
        "alter table if exists index_definitions add column if not exists granularity varchar(20) not null default 'monthly'",
        # scheduled_syncs 表（create_all 会建新表，此处兜底）
        """create table if not exists scheduled_syncs (
            id serial primary key,
            name varchar(120) not null,
            sync_type varchar(40) not null,
            sub_metric_id integer,
            months integer not null default 12,
            cron_minute varchar(20) not null default '0',
            cron_hour varchar(20) not null default '2',
            cron_day varchar(20) not null default '*',
            cron_month varchar(20) not null default '*',
            cron_dow varchar(20) not null default '*',
            enabled boolean not null default true,
            last_run_at timestamp,
            last_status varchar(20),
            last_message text,
            created_by varchar(120) not null default '',
            created_at timestamp not null default now(),
            updated_at timestamp not null default now()
        )""",
        """create table if not exists teams_bot_conversations (
            id serial primary key,
            conversation_id varchar(260) not null,
            service_url text not null,
            tenant_id varchar(120) not null default '',
            team_id varchar(160) not null default '',
            channel_id varchar(160) not null default '',
            conversation_type varchar(40) not null default '',
            name varchar(240) not null default '',
            user_aad_object_id varchar(160) not null default '',
            user_name varchar(240) not null default '',
            raw_activity text not null default '',
            welcome_sent_at timestamp,
            last_seen_at timestamp not null default now(),
            created_at timestamp not null default now(),
            updated_at timestamp not null default now()
        )""",
        "alter table if exists teams_bot_conversations add column if not exists welcome_sent_at timestamp",
        "create unique index if not exists uq_teams_bot_conversation_id on teams_bot_conversations(conversation_id)",
        """create table if not exists index_notification_configs (
            id serial primary key,
            index_code varchar(40) not null,
            index_name varchar(120) not null,
            teams_conversation_id integer,
            cron_minute varchar(20) not null default '0',
            cron_hour varchar(20) not null default '9',
            cron_day varchar(20) not null default '*',
            cron_month varchar(20) not null default '*',
            cron_dow varchar(20) not null default '*',
            enabled boolean not null default false,
            last_run_at timestamp,
            last_status varchar(20),
            last_message text,
            updated_by varchar(120) not null default '',
            created_at timestamp not null default now(),
            updated_at timestamp not null default now()
        )""",
        "create unique index if not exists uq_index_notification_code on index_notification_configs(index_code)",
        "update index_notification_configs set cron_day='*', cron_month='*', cron_dow='*' "
        "where cron_day is distinct from '*' or cron_month is distinct from '*' or cron_dow is distinct from '*'",
    ]:
        try:
            with engine.begin() as conn:
                conn.execute(text(_sql))
        except Exception:
            pass


_NULLABLE_FK_SQLS = [
    f"alter table if exists {tbl} alter column batch_id drop not null"
    for tbl in [
        "dwd_production_monitoring_daily",
        "dwd_akp_density_daily",
        "dwd_harvester_attendance_daily",
        "dwd_production_budget_monthly",
        "dwd_production_estimate_daily",
    ]
] + [
    f"alter table if exists {tbl} alter column file_id drop not null"
    for tbl in [
        "dwd_production_monitoring_daily",
        "dwd_akp_density_daily",
        "dwd_harvester_attendance_daily",
        "dwd_production_budget_monthly",
        "dwd_production_estimate_daily",
    ]
] + [
    f"alter table if exists {tbl} alter column source_record_id drop not null"
    for tbl in [
        "dwd_production_monitoring_daily",
        "dwd_akp_density_daily",
        "dwd_harvester_attendance_daily",
        "dwd_production_budget_monthly",
        "dwd_production_estimate_daily",
    ]
]

_UNIQUE_INDEX_SQLS = [
    "create unique index if not exists uq_dwd_production_monitoring on dwd_production_monitoring_daily(report_date, site, department, division, row_label)",
    "create unique index if not exists uq_dwd_akp_density on dwd_akp_density_daily(report_date, site, department, division, blok, row_label)",
    "create unique index if not exists uq_dwd_harvester_attendance on dwd_harvester_attendance_daily(report_date, site, department, section, worker_type, afdeling, row_label)",
    "create unique index if not exists uq_dwd_production_budget on dwd_production_budget_monthly(report_date, site, department, division, row_label)",
    "create unique index if not exists uq_dwd_production_estimate on dwd_production_estimate_daily(report_date, site, department, division, row_label)",
]


def _bootstrap_admin() -> None:
    from app.core.security import hash_password
    from app.models import User

    with SessionLocal() as db:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="管理员",
                role="admin",
            )
            db.add(admin)
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
