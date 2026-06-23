"""定时同步任务管理 API"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db import get_db
from app.models import ScheduledSync, User

router = APIRouter(tags=["scheduled-sync"])


# ── Schemas ───────────────────────────────────────────────────────

class ScheduledSyncIn(BaseModel):
    name: str
    sync_type: str                     # sub_metric | sap_harvest | agri_production
    sub_metric_id: Optional[int] = None
    months: int = 12
    cron_minute: str = "0"
    cron_hour: str = "2"
    cron_day: str = "*"
    cron_month: str = "*"
    cron_dow: str = "*"
    enabled: bool = True


class ScheduledSyncOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sync_type: str
    sub_metric_id: Optional[int]
    months: int
    cron_minute: str
    cron_hour: str
    cron_day: str
    cron_month: str
    cron_dow: str
    enabled: bool
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    last_message: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/scheduled-syncs", response_model=list[ScheduledSyncOut])
def list_scheduled_syncs(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    return db.query(ScheduledSync).order_by(ScheduledSync.id).all()


@router.post("/scheduled-syncs", response_model=ScheduledSyncOut, status_code=201)
def create_scheduled_sync(
    body: ScheduledSyncIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    _validate_sync_type(body)
    job = ScheduledSync(**body.model_dump(), created_by=user.username)
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.services.scheduler import reload_job
    reload_job(job)
    return job


@router.put("/scheduled-syncs/{job_id}", response_model=ScheduledSyncOut)
def update_scheduled_sync(
    job_id: int,
    body: ScheduledSyncIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    job = db.get(ScheduledSync, job_id)
    if not job:
        raise HTTPException(404, "定时任务不存在")
    _validate_sync_type(body)
    for k, v in body.model_dump().items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)

    from app.services.scheduler import reload_job
    reload_job(job)
    return job


@router.delete("/scheduled-syncs/{job_id}", status_code=204)
def delete_scheduled_sync(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    job = db.get(ScheduledSync, job_id)
    if not job:
        raise HTTPException(404, "定时任务不存在")
    db.delete(job)
    db.commit()

    from app.services.scheduler import remove_job
    remove_job(job_id)


@router.post("/scheduled-syncs/{job_id}/run", response_model=ScheduledSyncOut)
def trigger_scheduled_sync(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """立即手动触发一次定时任务（后台执行）。"""
    import threading
    from app.services.scheduler import _RUNNERS

    job = db.get(ScheduledSync, job_id)
    if not job:
        raise HTTPException(404, "定时任务不存在")
    runner = _RUNNERS.get(job.sync_type)
    if not runner:
        raise HTTPException(400, f"未知同步类型：{job.sync_type}")

    thread = threading.Thread(target=runner, args=[job_id], daemon=True)
    thread.start()

    db.refresh(job)
    return job


# ── Helpers ───────────────────────────────────────────────────────

def _validate_sync_type(body: ScheduledSyncIn) -> None:
    valid = {"sub_metric", "sap_harvest", "agri_production"}
    if body.sync_type not in valid:
        raise HTTPException(400, f"sync_type 必须是：{', '.join(sorted(valid))}")
    if body.sync_type in ("sub_metric", "agri_production") and not body.sub_metric_id:
        raise HTTPException(400, "sub_metric 和 agri_production 类型需要提供 sub_metric_id")
