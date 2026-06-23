from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_roles
from app.db import get_db
from app.models import TeamsBotConversation, User
from app.services.teams_bot import send_adaptive_card, upsert_conversation, verify_incoming_token

router = APIRouter(tags=["teams-bot"])


class TeamsBotConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    tenant_id: str
    team_id: str
    channel_id: str
    conversation_type: str
    name: str
    user_aad_object_id: str
    user_name: str
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class TeamsBotStatusOut(BaseModel):
    app_id_configured: bool
    app_password_configured: bool
    validate_incoming: bool
    messaging_endpoint: str


@router.post("/teams-bot/messages")
async def receive_teams_bot_activity(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Bot Framework Messaging endpoint: stores conversation references."""
    try:
        verify_incoming_token(authorization)
    except Exception as exc:
        raise HTTPException(401, f"Teams Bot 请求校验失败：{exc}")

    activity: dict[str, Any] = await request.json()
    activity_type = activity.get("type")
    if activity_type in {"message", "conversationUpdate", "installationUpdate"}:
        try:
            upsert_conversation(db, activity)
        except Exception as exc:
            raise HTTPException(400, f"保存 Teams 会话失败：{exc}")
    return {"ok": True}


@router.get("/teams-bot/status", response_model=TeamsBotStatusOut)
def get_teams_bot_status(
    _user: User = Depends(require_roles("admin", "analyst")),
):
    return TeamsBotStatusOut(
        app_id_configured=bool(settings.teams_bot_app_id),
        app_password_configured=bool(settings.teams_bot_app_password),
        validate_incoming=settings.teams_bot_validate_incoming,
        messaging_endpoint="/api/teams-bot/messages",
    )


@router.get("/teams-bot/conversations", response_model=list[TeamsBotConversationOut])
def list_teams_bot_conversations(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    return (
        db.query(TeamsBotConversation)
        .order_by(TeamsBotConversation.last_seen_at.desc(), TeamsBotConversation.id.desc())
        .all()
    )


@router.post("/teams-bot/conversations/{conversation_pk}/test")
def test_teams_bot_conversation(
    conversation_pk: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    target = db.get(TeamsBotConversation, conversation_pk)
    if not target:
        raise HTTPException(404, "Teams Bot 目标不存在")
    try:
        result = send_adaptive_card(
            target,
            title="经营指数平台 Bot 测试",
            lines=[
                "如果你能看到这条消息，说明 Bot 主动推送链路已经打通。",
                f"发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ],
            link_url=settings.teams_portal_url,
            link_label="系统链接",
        )
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "response": result}
