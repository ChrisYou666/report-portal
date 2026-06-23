from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db import get_db
from app.models import IndexNotificationConfig, TeamsBotConversation, User
from app.services.index_notifications import ensure_index_notification_defaults, preview_index_notification, send_index_notification

router = APIRouter(tags=["index-notifications"])


class IndexNotificationIn(BaseModel):
    teams_conversation_id: Optional[int] = None
    cron_minute: str = "0"
    cron_hour: str = "9"
    cron_day: str = "*"
    cron_month: str = "*"
    cron_dow: str = "*"
    enabled: bool = False


class IndexNotificationOut(BaseModel):
    id: int
    index_code: str
    index_name: str
    teams_conversation_id: Optional[int]
    teams_conversation_name: str = ""
    cron_minute: str
    cron_hour: str
    cron_day: str
    cron_month: str
    cron_dow: str
    enabled: bool
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    last_message: Optional[str]
    updated_by: str
    updated_at: datetime


class IndexNotificationPreviewOut(BaseModel):
    title: str
    lines: list[str]
    url: str


def _out(db: Session, cfg: IndexNotificationConfig) -> IndexNotificationOut:
    target_name = ""
    if cfg.teams_conversation_id:
        target = db.get(TeamsBotConversation, cfg.teams_conversation_id)
        target_name = target.name if target else ""
    return IndexNotificationOut(
        id=cfg.id,
        index_code=cfg.index_code,
        index_name=cfg.index_name,
        teams_conversation_id=cfg.teams_conversation_id,
        teams_conversation_name=target_name,
        cron_minute=cfg.cron_minute,
        cron_hour=cfg.cron_hour,
        cron_day=cfg.cron_day,
        cron_month=cfg.cron_month,
        cron_dow=cfg.cron_dow,
        enabled=cfg.enabled,
        last_run_at=cfg.last_run_at,
        last_status=cfg.last_status,
        last_message=cfg.last_message,
        updated_by=cfg.updated_by,
        updated_at=cfg.updated_at,
    )


@router.get("/index-notifications", response_model=list[IndexNotificationOut])
def list_index_notifications(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    configs = ensure_index_notification_defaults(db)
    return [_out(db, cfg) for cfg in configs]


@router.put("/index-notifications/{index_code}", response_model=IndexNotificationOut)
def update_index_notification(
    index_code: str,
    body: IndexNotificationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    configs = ensure_index_notification_defaults(db)
    cfg = next((item for item in configs if item.index_code == index_code), None)
    if not cfg:
        raise HTTPException(404, "指标通知配置不存在")
    if body.teams_conversation_id and not db.get(TeamsBotConversation, body.teams_conversation_id):
        raise HTTPException(400, "Teams Bot 目标不存在")
    for k, v in body.model_dump().items():
        setattr(cfg, k, v)
    cfg.updated_by = user.username
    db.commit()
    db.refresh(cfg)

    from app.services.scheduler import reload_index_notification
    reload_index_notification(cfg)
    return _out(db, cfg)


@router.get("/index-notifications/{index_code}/preview", response_model=IndexNotificationPreviewOut)
def preview_notification(
    index_code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    cfg = next((item for item in ensure_index_notification_defaults(db) if item.index_code == index_code), None)
    if not cfg:
        raise HTTPException(404, "指标通知配置不存在")
    return preview_index_notification(db, cfg.index_code, cfg.index_name)


@router.post("/index-notifications/{index_code}/test", response_model=IndexNotificationOut)
def test_index_notification(
    index_code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    cfg = next((item for item in ensure_index_notification_defaults(db) if item.index_code == index_code), None)
    if not cfg:
        raise HTTPException(404, "指标通知配置不存在")
    try:
        send_index_notification(db, cfg.id, force=True)
    except Exception:
        db.refresh(cfg)
        return _out(db, cfg)
    db.refresh(cfg)
    return _out(db, cfg)
