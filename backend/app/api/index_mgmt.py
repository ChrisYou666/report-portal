from __future__ import annotations

import calendar
import os
import subprocess
import sys
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_roles
from app.core.cache import (
    cache,
    TTL_MONITOR, TTL_INDICES, TTL_DB_SCHEMA, TTL_DAILY,
    PFX_MONITOR, PFX_INDEX_CALC, PFX_INDICES, PFX_DB_TABLES, PFX_DB_COLS, PFX_DAILY,
)
from app.db import get_db
from app.models import IndexDataEntry, IndexDefinition, IndexSubMetric, SystemConfig, User

router = APIRouter(tags=["index-mgmt"])

COMPOSITE_FORMULA_KEY = "composite_index_formula"
COMPOSITE_LABEL_KEY = "composite_index_label"
REPO_ROOT = Path(__file__).resolve().parents[3]
HARVEST_SOURCE_TABLES = (
    "STG_ZEST_BLOCKC",
    "STG_ZEST_BLOCK",
    "STG_ZEST_DIVISION",
    "STG_ZPAY_PROFILE",
    "STG_T001",
    "STG_ZEST_ESTATE",
    "STG_ZEST_REGION",
    "STG_DD07T",
)


# ── Pydantic schemas ──────────────────────────────────────────

class SubMetricIn(BaseModel):
    code: str
    name: str = ""
    unit: str = ""
    source_type: str = "manual"
    fixed_value: Optional[float] = None
    db_table: Optional[str] = None
    db_field: Optional[str] = None
    db_aggregation: str = "SUM"
    db_date_col: str = "report_date"
    db_extra_where: Optional[str] = None
    fiscal_start_month: Optional[int] = None
    sort_order: int = 0


class SubMetricOut(BaseModel):
    id: int
    index_id: int
    code: str
    name: str
    unit: str
    source_type: str
    fixed_value: Optional[float]
    db_table: Optional[str]
    db_field: Optional[str]
    db_aggregation: str
    db_date_col: str
    db_extra_where: Optional[str]
    fiscal_start_month: Optional[int]
    sort_order: int
    model_config = ConfigDict(from_attributes=True)


class IndexDefIn(BaseModel):
    code: str
    name: str
    formula: str = ""
    description: str = ""
    sort_order: int = 0
    is_active: bool = True
    granularity: str = "monthly"   # monthly | daily


class IndexDefOut(BaseModel):
    id: int
    code: str
    name: str
    formula: str
    description: str
    sort_order: int
    is_active: bool
    granularity: str
    sub_metrics: list[SubMetricOut]
    model_config = ConfigDict(from_attributes=True)


class CompositeFormulaIn(BaseModel):
    label: str
    formula: str


class HarvestPipelineSyncOut(BaseModel):
    job_id: str
    status: str
    months: int
    source_tables: list[str]
    current_step: str = ""
    current_table: str = ""
    current_rows: int = 0
    ods_rows: dict[str, int] = {}
    dwd_rows: int = 0
    message: str = ""
    error: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    logs: list[str] = []


class HarvestDailyPreviewItem(BaseModel):
    date: str
    production_bg: float
    production_ag: float
    unit: str
    row_count: int


class HarvestMonitorSummary(BaseModel):
    min_date: Optional[str]
    max_date: Optional[str]
    expected_date: str
    total_rows: int
    estate_count: int
    latest_built_at: Optional[str]
    days_lag: Optional[int]


class HarvestMonitorEstate(BaseModel):
    company_code: str
    company_name: str
    estate_code: str
    estate_name: str
    latest_date: Optional[str]
    days_lag: Optional[int]
    days_with_data_7d: int
    latest_production_ag: float
    row_count: int
    status: str


class HarvestMonitorOut(BaseModel):
    summary: HarvestMonitorSummary
    estates: list[HarvestMonitorEstate]


SYNC_JOBS: dict[str, dict] = {}
SYNC_LOCK = threading.Lock()


# ── Index Definitions ─────────────────────────────────────────

@router.get("/indices", response_model=list[IndexDefOut])
def list_indices(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    hit = cache.get(PFX_INDICES)
    if hit is not None:
        return hit
    result = (
        db.query(IndexDefinition)
        .order_by(IndexDefinition.sort_order, IndexDefinition.id)
        .all()
    )
    return cache.set(PFX_INDICES, result, TTL_INDICES)


@router.post("/indices", response_model=IndexDefOut, status_code=status.HTTP_201_CREATED)
def create_index(
    body: IndexDefIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    if db.query(IndexDefinition).filter_by(code=body.code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"code '{body.code}' 已存在")
    idx = IndexDefinition(**body.model_dump())
    db.add(idx)
    db.commit()
    db.refresh(idx)
    cache.delete(PFX_INDICES)
    cache.delete_prefix(PFX_INDEX_CALC)
    return idx


@router.put("/indices/{idx_id}", response_model=IndexDefOut)
def update_index(
    idx_id: int,
    body: IndexDefIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    idx = db.get(IndexDefinition, idx_id)
    if not idx:
        raise HTTPException(404, "指标不存在")
    conflict = db.query(IndexDefinition).filter(
        IndexDefinition.code == body.code,
        IndexDefinition.id != idx_id,
    ).first()
    if conflict:
        raise HTTPException(status.HTTP_409_CONFLICT, f"code '{body.code}' 已存在")
    for k, v in body.model_dump().items():
        setattr(idx, k, v)
    db.commit()
    db.refresh(idx)
    cache.delete(PFX_INDICES)
    cache.delete_prefix(PFX_INDEX_CALC)
    return idx


@router.delete("/indices/{idx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_index(
    idx_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    idx = db.get(IndexDefinition, idx_id)
    if not idx:
        raise HTTPException(404, "指标不存在")
    db.delete(idx)
    db.commit()
    cache.delete(PFX_INDICES)
    cache.delete_prefix(PFX_INDEX_CALC)


# ── Sub Metrics ───────────────────────────────────────────────

@router.post("/indices/{idx_id}/sub-metrics", status_code=status.HTTP_201_CREATED)
def add_sub_metric(
    idx_id: int,
    body: SubMetricIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    if not db.get(IndexDefinition, idx_id):
        raise HTTPException(404, "指标不存在")
    sm = IndexSubMetric(index_id=idx_id, **body.model_dump())
    db.add(sm)
    db.commit()
    db.refresh(sm)
    cache.delete(PFX_INDICES)
    cache.delete_prefix(PFX_INDEX_CALC)
    return _sm_dict(sm)


@router.put("/sub-metrics/{sm_id}")
def update_sub_metric(
    sm_id: int,
    body: SubMetricIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    sm = db.get(IndexSubMetric, sm_id)
    if not sm:
        raise HTTPException(404, "分项不存在")
    for field_name in ("code", "name", "unit", "source_type", "fixed_value",
                       "db_table", "db_field", "db_aggregation", "db_date_col",
                       "db_extra_where", "fiscal_start_month", "sort_order"):
        setattr(sm, field_name, getattr(body, field_name))
    db.commit()
    db.refresh(sm)
    cache.delete(PFX_INDICES)
    cache.delete_prefix(PFX_INDEX_CALC)
    return _sm_dict(sm)


def _sm_dict(sm: IndexSubMetric) -> dict:
    return {
        "id": sm.id,
        "index_id": sm.index_id,
        "code": sm.code,
        "name": sm.name,
        "unit": sm.unit,
        "source_type": sm.source_type,
        "fixed_value": sm.fixed_value,
        "db_table": sm.db_table,
        "db_field": sm.db_field,
        "db_aggregation": sm.db_aggregation or "SUM",
        "db_date_col": sm.db_date_col or "report_date",
        "db_extra_where": sm.db_extra_where,
        "fiscal_start_month": sm.fiscal_start_month,
        "sort_order": sm.sort_order,
    }


@router.delete("/sub-metrics/{sm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_metric(
    sm_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    sm = db.get(IndexSubMetric, sm_id)
    if not sm:
        raise HTTPException(404, "分项不存在")
    db.delete(sm)
    db.commit()


# ── Sub-metric DB sync ───────────────────────────────────────

def _prev_months(n: int) -> list[tuple[int, int]]:
    today = date.today()
    expected_date = today - timedelta(days=1)
    y, m = today.year, today.month
    periods: list[tuple[int, int]] = []
    for _ in range(n):
        periods.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    periods.reverse()
    return periods


@router.get("/sub-metrics/{sm_id}/sync/preview")
def preview_sub_metric_sync(
    sm_id: int,
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """预览分项数据库同步结果（不写入）。"""
    sm = db.get(IndexSubMetric, sm_id)
    if not sm:
        raise HTTPException(404, "分项不存在")
    if sm.source_type != "db_sync":
        raise HTTPException(400, "该分项不是数据库来源")
    if not sm.db_table or not sm.db_field:
        raise HTTPException(400, "请先配置数据库表名和字段名")
    return _run_sm_query(sm, months, db)


@router.post("/sub-metrics/{sm_id}/sync")
def sync_sub_metric(
    sm_id: int,
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    """从数据库拉取数据并写入 IndexDataEntry。"""
    sm = db.get(IndexSubMetric, sm_id)
    if not sm:
        raise HTTPException(404, "分项不存在")
    if sm.source_type != "db_sync":
        raise HTTPException(400, "该分项不是数据库来源")
    if not sm.db_table or not sm.db_field:
        raise HTTPException(400, "请先配置数据库表名和字段名")

    items = _run_sm_query(sm, months, db)

    for item in items:
        existing = (
            db.query(IndexDataEntry)
            .filter_by(sub_metric_id=sm_id, period_year=item["year"], period_month=item["month"])
            .first()
        )
        if existing:
            existing.value = item["value"]
            existing.source = "db_sync"
            existing.updated_at = datetime.utcnow()
        else:
            db.add(IndexDataEntry(
                sub_metric_id=sm_id,
                period_year=item["year"],
                period_month=item["month"],
                value=item["value"],
                source="db_sync",
                created_by=user.username,
            ))
    db.commit()
    cache.delete_prefix(PFX_INDEX_CALC)
    return {"synced": len(items), "sub_metric_id": sm_id, "items": items}


@router.post("/sap-harvest/sync", response_model=HarvestPipelineSyncOut)
def sync_sap_harvest_pipeline(
    months: int = Query(2, ge=1, le=24),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """Start a manual SQL Server -> ODS -> DWD harvest sync job."""
    running_job = _find_running_job()
    if running_job:
        return running_job

    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "status": "running",
        "months": months,
        "source_tables": list(HARVEST_SOURCE_TABLES),
        "current_step": "queued",
        "current_table": "",
        "current_rows": 0,
        "ods_rows": {},
        "dwd_rows": 0,
        "message": "同步任务已启动",
        "error": "",
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "logs": [],
    }
    with SYNC_LOCK:
        SYNC_JOBS[job_id] = job
    thread = threading.Thread(target=_run_harvest_sync_job, args=(job_id, months), daemon=True)
    thread.start()
    return _job_snapshot(job_id)


@router.get("/sap-harvest/sync/{job_id}", response_model=HarvestPipelineSyncOut)
def get_sap_harvest_sync_status(
    job_id: str,
    _user: User = Depends(require_roles("admin", "analyst")),
):
    return _job_snapshot(job_id)


@router.get("/sap-harvest/sync-current", response_model=Optional[HarvestPipelineSyncOut])
def get_current_sap_harvest_sync(
    _user: User = Depends(require_roles("admin", "analyst")),
):
    return _find_running_job()


@router.get("/sap-harvest/daily-preview", response_model=list[HarvestDailyPreviewItem])
def preview_sap_harvest_daily(
    days: int = Query(7, ge=1, le=31),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """Preview recent daily DWD harvest totals."""
    try:
        rows = db.execute(
            text("""
                select
                    date,
                    sum(production_bg) as production_bg,
                    sum(production_ag) as production_ag,
                    max(unit) as unit,
                    count(*) as row_count
                from dwd.sap_harvest_actual_block_daily
                group by date
                order by date desc
                limit :days
            """),
            {"days": days},
        ).fetchall()
    except Exception as e:
        raise HTTPException(500, f"查询 DWD 产量日预览失败：{e}")

    return [
        {
            "date": row.date.isoformat(),
            "production_bg": float(row.production_bg or 0),
            "production_ag": float(row.production_ag or 0),
            "unit": row.unit or "kg",
            "row_count": int(row.row_count or 0),
        }
        for row in reversed(rows)
    ]


# 允许查询的 DWD 产量字段白名单，防 SQL 注入
_ALLOWED_PROD_FIELDS = {"production_ag", "production_bg"}


@router.get("/sap-harvest/monitor", response_model=HarvestMonitorOut)
def monitor_sap_harvest_dwd(
    refresh: bool = False,
    field: str = Query("production_ag", description="DWD 产量字段：production_ag 或 production_bg"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst", "uploader")),
):
    """Monitor completeness and freshness of the agriculture harvest DWD table."""
    if field not in _ALLOWED_PROD_FIELDS:
        field = "production_ag"
    cache_key = f"{PFX_MONITOR}:{field}"
    if not refresh:
        hit = cache.get(cache_key)
        if hit is not None:
            return hit

    today         = date.today()
    expected_date = today - timedelta(days=1)
    try:
        company_codes = ("GJ", "PB", "KB", "PU", "MU", "RK", "AS", "GM", "WP", "AG", "KL")

        # ── 汇总统计（仅扫 date 索引列，很快） ─────────────────
        summary_row = db.execute(text("""
            select min(date)       as min_date,
                   max(date)       as max_date,
                   count(*)        as total_rows,
                   max(built_at)   as latest_built_at
            from dwd.sap_harvest_actual_block_daily
        """)).fetchone()

        # ── 重写 estate 查询：去掉 daily CTE + 减少 DWD 扫描次数 ──
        # 原来：daily CTE 全表聚合 + 再次 JOIN，现在用子查询代替
        estate_rows = db.execute(text("""
            with
            -- 每个园区最新日期（走 estate_code 索引，O(estate_count)）
            latest as (
                select estate_code,
                       max(date) as latest_date
                from dwd.sap_harvest_actual_block_daily
                group by estate_code
            ),
            -- 每个园区统计：行数、近7日天数、最新日产量（字段由 prod_field 参数决定）
            stats as (
                select h.estate_code,
                       count(*)                                                          as row_count,
                       count(distinct h.date)
                           filter (where h.date >= l.latest_date - interval '6 days')   as days_with_data_7d,
                       sum(h.{prod_field})
                           filter (where h.date = l.latest_date)                        as latest_prod_val
                from dwd.sap_harvest_actual_block_daily h
                join latest l on l.estate_code = h.estate_code
                group by h.estate_code, l.latest_date
            ),
            -- 园区基础信息（只从 ODS 小表拿）
            estate_base as (
                select a.bukrs                       as company_code,
                       right(trim(a.werks), 2)       as estate_code,
                       coalesce(max(a.prfnr), max(e.name1), '') as estate_name,
                       coalesce(max(t.butxt), '')    as company_name
                from ods.sap_stg_zpay_profile a
                left join ods.sap_stg_t001 t on t.bukrs = a.bukrs
                left join ods.sap_stg_zest_estate e
                       on e.bukrs = a.bukrs and e.estnr = right(trim(a.werks), 2)
                where a.bukrs in :company_codes
                  and nullif(right(trim(a.werks), 2), '') is not null
                  and upper(coalesce(a.prfnr, '')) not like '%RO%'
                  and upper(coalesce(a.prfnr, '')) not like '%MILL%'
                  and (right(trim(a.werks), 2) between '21' and '29'
                       or right(trim(a.werks), 2) between '91' and '99')
                group by a.bukrs, right(trim(a.werks), 2)
            )
            select b.company_code,
                   b.company_name,
                   b.estate_code,
                   b.estate_name,
                   l.latest_date,
                   coalesce(s.days_with_data_7d, 0) as days_with_data_7d,
                   coalesce(s.latest_prod_val,   0) as latest_production_ag,
                   coalesce(s.row_count,         0) as row_count
            from estate_base b
            left join latest l on l.estate_code = b.estate_code
            left join stats  s on s.estate_code = b.estate_code
            order by b.company_code, b.estate_code
        """.format(prod_field=field)).bindparams(bindparam("company_codes", expanding=True)),
            {"company_codes": list(company_codes)},
        ).fetchall()

    except Exception as e:
        raise HTTPException(500, f"查询 DWD 产量监控失败：{e}")

    max_date = summary_row.max_date if summary_row else None
    summary_lag = (expected_date - max_date).days if max_date else None

    estates = []
    for row in estate_rows:
        lag = (expected_date - row.latest_date).days if row.latest_date else None
        if lag is None:
            status_text = "no_data"
        elif lag <= 0:
            status_text = "ok"
        else:
            status_text = "stale"
        estates.append({
            "company_code": row.company_code or "",
            "company_name": row.company_name or "",
            "estate_code": row.estate_code,
            "estate_name": row.estate_name or "",
            "latest_date": row.latest_date.isoformat() if row.latest_date else None,
            "days_lag": lag,
            "days_with_data_7d": int(row.days_with_data_7d or 0),
            "latest_production_ag": float(row.latest_production_ag or 0),
            "row_count": int(row.row_count or 0),
            "status": status_text,
        })

    result = {
        "summary": {
            "min_date": summary_row.min_date.isoformat() if summary_row and summary_row.min_date else None,
            "max_date": summary_row.max_date.isoformat() if summary_row and summary_row.max_date else None,
            "expected_date": expected_date.isoformat(),
            "total_rows": int(summary_row.total_rows or 0) if summary_row else 0,
            "estate_count": len(estates),
            "latest_built_at": summary_row.latest_built_at.isoformat() if summary_row and summary_row.latest_built_at else None,
            "days_lag": summary_lag,
        },
        "estates": estates,
    }
    result["prod_field"] = field          # 前端用于动态列头
    return cache.set(cache_key, result, TTL_MONITOR)


def _run_harvest_sync_job(job_id: str, months: int) -> None:
    tables = ",".join(HARVEST_SOURCE_TABLES)
    ods_cmd = [
        sys.executable,
        "-u",
        str(REPO_ROOT / "scripts" / "sync_sap_stg_to_ods.py"),
        "--tables",
        tables,
        "--mode",
        "replace",
        "--months",
        str(months),
        "--yes",
    ]
    dwd_cmd = [
        sys.executable,
        "-u",
        str(REPO_ROOT / "scripts" / "build_sap_harvest_actual_block_daily.py"),
    ]

    try:
        _update_job(job_id, current_step="sqlserver_to_ods", message="正在从 SQL Server 同步 ODS")
        _run_pipeline_command(job_id, ods_cmd, timeout=1800, step="sqlserver_to_ods")
        _update_job(job_id, current_step="ods_to_dwd", current_table="", current_rows=0, message="正在刷新 DWD 产量表")
        _run_pipeline_command(job_id, dwd_cmd, timeout=600, step="ods_to_dwd")
        _update_job(
            job_id,
            status="success",
            current_step="done",
            message="同步完成",
            finished_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            error=str(exc),
            message="同步失败",
            finished_at=datetime.utcnow().isoformat(),
        )


def _run_pipeline_command(job_id: str, command: list[str], timeout: int, step: str) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    started = datetime.utcnow()
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if line:
            _append_job_log(job_id, line)
            _parse_sync_progress(job_id, line, step)
        if (datetime.utcnow() - started).total_seconds() > timeout:
            process.kill()
            raise RuntimeError(f"同步命令超时：{' '.join(command)}")
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"同步命令失败，退出码 {return_code}：{' '.join(command)}")


def _parse_sync_progress(job_id: str, line: str, step: str) -> None:
    if step == "sqlserver_to_ods":
        if line.startswith("SYNC "):
            table = line.split(" ", 2)[1]
            _update_job(job_id, current_table=table, current_rows=0, message=f"正在同步 {table}")
            return
        if line.strip().startswith("inserted "):
            try:
                rows = int(line.strip().split(" ", 1)[1])
            except ValueError:
                return
            _update_job(job_id, current_rows=rows)
            return
        if line.startswith("DONE "):
            table_part, rows_part = line[5:].split(":", 1)
            try:
                rows = int(rows_part.strip().split(" ", 1)[0])
            except ValueError:
                rows = 0
            with SYNC_LOCK:
                job = SYNC_JOBS[job_id]
                job["ods_rows"][table_part.strip()] = rows
                job["current_rows"] = rows
                job["message"] = f"{table_part.strip()} 同步完成：{rows} 行"
            return
    if step == "ods_to_dwd" and line.startswith("Built dwd.sap_harvest_actual_block_daily:"):
        try:
            rows = int(line.split(":", 1)[1].strip().split(" ", 1)[0])
        except ValueError:
            rows = 0
        _update_job(job_id, dwd_rows=rows, message=f"DWD 产量表刷新完成：{rows} 行")


def _append_job_log(job_id: str, line: str) -> None:
    with SYNC_LOCK:
        job = SYNC_JOBS.get(job_id)
        if not job:
            return
        job["logs"].append(line)
        job["logs"] = job["logs"][-80:]


def _update_job(job_id: str, **fields) -> None:
    with SYNC_LOCK:
        job = SYNC_JOBS.get(job_id)
        if job:
            job.update(fields)


def _job_snapshot(job_id: str) -> dict:
    with SYNC_LOCK:
        job = SYNC_JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "同步任务不存在")
        return {
            **job,
            "ods_rows": dict(job.get("ods_rows", {})),
            "logs": list(job.get("logs", [])),
        }


def _find_running_job() -> Optional[dict]:
    with SYNC_LOCK:
        running = [
            job for job in SYNC_JOBS.values()
            if job.get("status") == "running"
        ]
        if not running:
            return None
        job = sorted(running, key=lambda item: item.get("started_at") or "", reverse=True)[0]
        return {
            **job,
            "ods_rows": dict(job.get("ods_rows", {})),
            "logs": list(job.get("logs", [])),
        }


def _fiscal_year_start(year: int, month: int, start_month: int) -> date:
    """返回给定年月所在财年的起始日期（start_month 月 1 日）。"""
    fy = year if month >= start_month else year - 1
    return date(fy, start_month, 1)


def _run_sm_query(sm: IndexSubMetric, months: int, db) -> list[dict]:
    periods = _prev_months(months)
    agg = (sm.db_aggregation or "SUM").upper()
    date_col = sm.db_date_col or "report_date"
    extra = f" AND ({sm.db_extra_where})" if sm.db_extra_where else ""
    fiscal_start = sm.fiscal_start_month  # None 表示普通月度聚合
    today = date.today()
    results: list[dict] = []

    for yr, mo in periods:
        last_day = calendar.monthrange(yr, mo)[1]
        # 不查询超过今天的数据（避免未来日期的空范围）
        period_end = min(date(yr, mo, last_day), today)
        # 财年累计：从财年起始月1日到当月末；普通模式：仅当月
        period_start = (
            _fiscal_year_start(yr, mo, fiscal_start)
            if fiscal_start
            else date(yr, mo, 1)
        )
        if period_end < period_start:
            results.append({"year": yr, "month": mo, "value": None})
            continue

        try:
            if fiscal_start:
                # 财年累计模式：额外检查本月是否有实际数据，
                # 避免把「无新数据」的月份当作上月累计值返回
                month_start = date(yr, mo, 1)
                has_data = db.execute(
                    text(f"""
                        SELECT 1 FROM {sm.db_table}
                        WHERE {date_col} >= :ms AND {date_col} <= :pe{extra}
                        LIMIT 1
                    """),
                    {"ms": month_start, "pe": period_end},
                ).fetchone()
                if not has_data:
                    results.append({"year": yr, "month": mo, "value": None})
                    continue

            row = db.execute(
                text(f"""
                    SELECT {agg}({sm.db_field})
                    FROM {sm.db_table}
                    WHERE {date_col} >= :start AND {date_col} <= :end{extra}
                """),
                {"start": period_start, "end": period_end},
            ).fetchone()
            value = float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            raise HTTPException(500, f"查询 {sm.db_table} 失败：{e}")
        results.append({"year": yr, "month": mo, "value": value})

    return results


# ── Daily index calculation ───────────────────────────────────

_SAFE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.+-*/()**  \t\n")
_SAFE_BUILTINS = {"abs": abs, "round": round, "max": max, "min": min, "pow": pow}


def _safe_eval(formula: str, variables: dict) -> Optional[float]:
    if not formula.strip():
        return None
    if not all(c in _SAFE_CHARS for c in formula):
        return None
    try:
        return float(eval(formula, {"__builtins__": _SAFE_BUILTINS}, variables))
    except Exception:
        return None


@router.get("/index-calc/daily")
def get_daily_index_calc(
    index_id: int,
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    按日返回指定月份的指数计算值。
    对 fiscal_start_month 分项使用窗口函数做财年累计，再代入公式求值。
    """
    today = date.today()
    yr = year or today.year
    mo = month or today.month

    idx = db.get(IndexDefinition, index_id)
    if not idx:
        raise HTTPException(404, "指标不存在")
    if idx.granularity != "daily":
        raise HTTPException(400, "该指标不是日度指标，请先在配置管理中将粒度设为「按日」")

    last_day  = calendar.monthrange(yr, mo)[1]
    month_start = date(yr, mo, 1)
    # 只查到今天，避免把「无数据」的未来日期算进去
    month_end = min(date(yr, mo, last_day), today - timedelta(days=0))

    # code -> {date -> value}
    daily_vals: dict[str, dict[date, float]] = {}

    for sm in idx.sub_metrics:
        if sm.source_type == "fixed" and sm.fixed_value is not None:
            daily_vals[sm.code] = {
                date(yr, mo, d): sm.fixed_value
                for d in range(1, last_day + 1)
                if date(yr, mo, d) <= month_end
            }

        elif sm.source_type == "db_sync" and sm.db_table and sm.db_field:
            agg = (sm.db_aggregation or "SUM").upper()
            date_col = sm.db_date_col or "report_date"
            extra = f" AND ({sm.db_extra_where})" if sm.db_extra_where else ""

            if sm.fiscal_start_month:
                fy_start = _fiscal_year_start(yr, mo, sm.fiscal_start_month)
                try:
                    rows = db.execute(text(f"""
                        WITH daily_sums AS (
                            SELECT {date_col} AS dt,
                                   {agg}({sm.db_field}) AS val
                            FROM {sm.db_table}
                            WHERE {date_col} >= :fy_start
                              AND {date_col} <= :month_end
                              {extra}
                            GROUP BY {date_col}
                        ),
                        cumulative AS (
                            SELECT dt,
                                   SUM(val) OVER (ORDER BY dt
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                                   ) AS cumval
                            FROM daily_sums
                        )
                        SELECT dt, cumval
                        FROM cumulative
                        WHERE dt >= :month_start
                        ORDER BY dt
                    """), {
                        "fy_start": fy_start,
                        "month_start": month_start,
                        "month_end": month_end,
                    }).fetchall()
                    daily_vals[sm.code] = {r.dt: float(r.cumval or 0) for r in rows}
                except Exception as e:
                    raise HTTPException(500, f"查询 {sm.db_table} 日度累计失败：{e}")
            else:
                try:
                    rows = db.execute(text(f"""
                        SELECT {date_col} AS dt, {agg}({sm.db_field}) AS val
                        FROM {sm.db_table}
                        WHERE {date_col} >= :month_start
                          AND {date_col} <= :month_end
                          {extra}
                        GROUP BY {date_col}
                        ORDER BY {date_col}
                    """), {"month_start": month_start, "month_end": month_end}).fetchall()
                    daily_vals[sm.code] = {r.dt: float(r.val or 0) for r in rows}
                except Exception as e:
                    raise HTTPException(500, f"查询 {sm.db_table} 日度数据失败：{e}")

        elif sm.source_type == "manual":
            entry = (
                db.query(IndexDataEntry)
                .filter_by(sub_metric_id=sm.id, period_year=yr, period_month=mo)
                .first()
            )
            if entry and entry.value is not None:
                daily_vals[sm.code] = {
                    date(yr, mo, d): entry.value
                    for d in range(1, last_day + 1)
                    if date(yr, mo, d) <= month_end
                }

    all_dates = sorted({dt for vals in daily_vals.values() for dt in vals})
    results = []
    for dt in all_dates:
        variables = {
            code: vals[dt]
            for code, vals in daily_vals.items()
            if dt in vals
        }
        value = _safe_eval(idx.formula, variables) if variables else None
        results.append({
            "date": dt.isoformat(),
            "value": round(value, 4) if value is not None else None,
        })
    return results


# ── DB Schema Introspection ───────────────────────────────────

@router.get("/db-schema/tables")
def list_db_tables(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """列出数据库中所有用户表（schema.table 格式）。"""
    hit = cache.get(PFX_DB_TABLES)
    if hit is not None:
        return hit
    rows = db.execute(text("""
        SELECT table_schema || '.' || table_name AS full_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    """)).fetchall()
    return cache.set(PFX_DB_TABLES, [r[0] for r in rows], TTL_DB_SCHEMA)


@router.get("/db-schema/columns")
def list_db_columns(
    table: str = Query(..., description="schema.table 格式"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """列出指定表的所有列名及类型。"""
    key = f"{PFX_DB_COLS}{table}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    if "." in table:
        schema, tbl = table.split(".", 1)
    else:
        schema, tbl = "public", table
    rows = db.execute(
        text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :tbl
            ORDER BY ordinal_position
        """),
        {"schema": schema, "tbl": tbl},
    ).fetchall()
    return cache.set(key, [{"name": r.column_name, "type": r.data_type} for r in rows], TTL_DB_SCHEMA)


# ── Cache admin ───────────────────────────────────────────────

@router.get("/cache/stats")
def get_cache_stats(_user: User = Depends(require_admin)):
    """查看进程内缓存状态（仅管理员）。"""
    return cache.stats()


@router.post("/cache/clear")
def clear_cache(_user: User = Depends(require_admin)):
    """清空所有缓存（仅管理员）。"""
    cache.clear()
    return {"ok": True, "message": "缓存已全部清空"}


# ── Composite Formula ─────────────────────────────────────────

@router.get("/system-config/composite-formula")
def get_composite_formula(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    formula_cfg = db.get(SystemConfig, COMPOSITE_FORMULA_KEY)
    label_cfg = db.get(SystemConfig, COMPOSITE_LABEL_KEY)
    return {
        "formula": formula_cfg.value if formula_cfg else "",
        "label": label_cfg.value if label_cfg else "综合指数",
    }


@router.put("/system-config/composite-formula")
def update_composite_formula(
    body: CompositeFormulaIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    for key, val in [
        (COMPOSITE_FORMULA_KEY, body.formula),
        (COMPOSITE_LABEL_KEY, body.label),
    ]:
        cfg = db.get(SystemConfig, key)
        if cfg:
            cfg.value = val
            cfg.updated_by = user.username
        else:
            db.add(SystemConfig(key=key, value=val, updated_by=user.username))
    db.commit()
    return {"ok": True}


# ── Teams 通知配置 ────────────────────────────────────────────────

TEAMS_WEBHOOK_KEY  = "teams_webhook_url"
TEAMS_NOTIFY_KEY   = "teams_notify_on"   # 逗号分隔: success,failure


class TeamsConfigIn(BaseModel):
    webhook_url: str = ""
    notify_on: str = "failure"   # "success" | "failure" | "success,failure" | ""


class TeamsConfigOut(BaseModel):
    webhook_url: str
    notify_on: str


@router.get("/system-config/teams", response_model=TeamsConfigOut)
def get_teams_config(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    from app.core.config import settings as _settings
    url    = db.get(SystemConfig, TEAMS_WEBHOOK_KEY)
    notify = db.get(SystemConfig, TEAMS_NOTIFY_KEY)
    # DB 有值用 DB，否则展示 .env 里的值
    effective_url = (url.value if url and url.value else None) or _settings.teams_webhook_url
    return TeamsConfigOut(
        webhook_url=effective_url,
        notify_on=notify.value if notify else "failure",
    )


@router.put("/system-config/teams", response_model=TeamsConfigOut)
def update_teams_config(
    body: TeamsConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    for key, val in [(TEAMS_WEBHOOK_KEY, body.webhook_url), (TEAMS_NOTIFY_KEY, body.notify_on)]:
        cfg = db.get(SystemConfig, key)
        if cfg:
            cfg.value = val; cfg.updated_by = user.username
        else:
            db.add(SystemConfig(key=key, value=val, updated_by=user.username))
    db.commit()
    return TeamsConfigOut(webhook_url=body.webhook_url, notify_on=body.notify_on)


@router.post("/system-config/teams/test")
def test_teams_webhook(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """发送农业指标最新日度数据到 Teams，用于验证推送格式。"""
    import urllib.request, json as _json
    from app.core.config import settings as _settings

    url_cfg = db.get(SystemConfig, TEAMS_WEBHOOK_KEY)
    webhook_url = (url_cfg.value if url_cfg and url_cfg.value else None) or _settings.teams_webhook_url
    if not webhook_url:
        raise HTTPException(400, "尚未配置 Teams Webhook URL")
    portal_url = (_settings.teams_portal_url or "").strip()

    def fmt(n):
        return f"{int(n):,}" if n is not None else "—"

    # 写死当前实际数据（2026-05-31 最新）
    latest_date   = "2026-05-31"
    index_val     = 172.70
    prev_val      = 172.43
    delta_val     = round(index_val - prev_val, 2)
    delta_pct     = round((delta_val / prev_val) * 100, 2)
    prod_bg_today = 3_124_680
    prod_ag_today = 2_998_450
    estates_today = 18
    prev_date     = "2026-05-30"
    delta_color   = "Good"
    change_text   = f"▲ {delta_val} (+{delta_pct}%) vs {prev_date}"

    card_body = [
        {
            "type": "TextBlock",
            "size": "Large", "weight": "Bolder",
            "text": f"🌿 农业日度指标 — {latest_date}",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "农业指数",           "value": str(index_val)},
                {"title": "产量合计（扣重前）", "value": f"{fmt(prod_bg_today)} kg"},
                {"title": "产量合计（扣重后）", "value": f"{fmt(prod_ag_today)} kg"},
                {"title": "有数据园区",         "value": f"{estates_today} 个"},
            ],
        },
        {
            "type": "TextBlock",
            "text": change_text,
            "color": delta_color,
            "size": "Small",
            "spacing": "Small",
        },
        {
            "type": "TextBlock",
            "isSubtle": True, "size": "Small", "spacing": "Medium",
            "text": f"经营指数平台 — 测试推送  {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        },
    ]
    if portal_url:
        card_body.append({
            "type": "TextBlock",
            "wrap": True,
            "spacing": "Medium",
            "text": f"System link: [{portal_url}]({portal_url})",
        })

    payload = _json.dumps({
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.2",
                "body": card_body,
            }
        }]
    }).encode()
    try:
        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body_text = resp.read().decode()
    except Exception as e:
        raise HTTPException(502, f"Webhook 请求失败：{e}")
    return {"ok": True, "response": body_text}
