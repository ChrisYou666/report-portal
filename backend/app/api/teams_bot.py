from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_roles
from app.db import get_db
from app.models import TeamsBotConversation, User
from app.services.teams_bot import send_adaptive_card, send_text_message, upsert_conversation, verify_incoming_token

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
    display_name_override: str = ""
    user_aad_object_id: str
    user_name: str
    display_name: str = ""
    display_detail: str = ""
    target_label: str = ""
    team_name: str = ""
    channel_name: str = ""
    sender_name: str = ""
    is_validation_target: bool = False
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class TeamsBotStatusOut(BaseModel):
    app_id_configured: bool
    app_password_configured: bool
    validate_incoming: bool
    messaging_endpoint: str


class TeamsBotConversationNameIn(BaseModel):
    display_name: str = ""


def _activity_text(activity: dict[str, Any]) -> str:
    raw_text = str(activity.get("text") or "")
    text = re.sub(r"<[^>]+>", " ", raw_text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_bot_command(activity: dict[str, Any]) -> bool:
    text = _activity_text(activity)
    if not text:
        return False
    return bool(re.search(r"\b(hi|hello|help)\b", text))


def _should_send_welcome(activity: dict[str, Any]) -> bool:
    activity_type = activity.get("type")
    if activity_type == "installationUpdate":
        return (activity.get("action") or "").lower() != "remove"
    if activity_type != "conversationUpdate":
        return False
    if activity.get("membersRemoved"):
        return False
    members_added = activity.get("membersAdded") or []
    if members_added:
        bot_id = (settings.teams_bot_app_id or "").lower()
        return any(not bot_id or str(member.get("id") or "").lower() == bot_id for member in members_added)
    return True


def _welcome_text() -> str:
    return (
        "Welcome to Report Portal Bot. "
        "I will send scheduled indicator notifications here. "
        f"Open portal: {settings.teams_portal_url}"
    )


def _command_reply_text() -> str:
    return (
        "Hi, Report Portal Bot is running. "
        f"Open portal: {settings.teams_portal_url}"
    )


def _raw_activity(row: TeamsBotConversation) -> dict[str, Any]:
    try:
        data = json.loads(row.raw_activity or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _short_id(value: str, keep: int = 8) -> str:
    if not value:
        return ""
    return value if len(value) <= keep * 2 + 3 else f"{value[:keep]}...{value[-keep:]}"


def _is_validation_target(row: TeamsBotConversation, activity: dict[str, Any]) -> bool:
    values = [
        row.name,
        row.user_name,
        (activity.get("conversation") or {}).get("name") or "",
        ((activity.get("channelData") or {}).get("team") or {}).get("name") or "",
        ((activity.get("channelData") or {}).get("channel") or {}).get("name") or "",
    ]
    return any(str(value).startswith("AppValidation-") for value in values)


def _conversation_display(row: TeamsBotConversation) -> dict[str, Any]:
    activity = _raw_activity(row)
    channel_data = activity.get("channelData") or {}
    conversation = activity.get("conversation") or {}
    sender = activity.get("from") or {}
    team = channel_data.get("team") or {}
    channel = channel_data.get("channel") or {}

    conv_type = row.conversation_type or conversation.get("conversationType") or ""
    team_name = team.get("name") or ""
    channel_name = channel.get("name") or ""
    sender_name = row.user_name or sender.get("name") or ""
    is_validation = _is_validation_target(row, activity)
    override_name = (row.display_name_override or "").strip()

    if override_name:
        raw_name = row.name or conversation.get("name") or _short_id(row.conversation_id)
        display_name = override_name
    elif is_validation:
        display_name = f"验证会话：{row.name or conversation.get('name') or _short_id(row.conversation_id)}"
    elif conv_type == "personal":
        display_name = f"个人：{sender_name or row.name or _short_id(row.conversation_id)}"
    elif conv_type == "channel":
        if team_name or channel_name:
            display_name = "频道：" + " / ".join(part for part in [team_name, channel_name] if part)
        elif row.name and row.name != "Teams 频道":
            display_name = f"频道：{row.name}"
        else:
            display_name = f"频道：{_short_id(row.channel_id or row.conversation_id)}"
    elif conv_type == "groupChat":
        display_name = f"群聊：{row.name or _short_id(row.conversation_id)}"
    else:
        display_name = row.name or sender_name or conv_type or f"目标 {row.id}"

    details = []
    if sender_name:
        details.append(f"用户 {sender_name}")
    if team_name:
        details.append(f"团队 {team_name}")
    if channel_name:
        details.append(f"频道 {channel_name}")
    if row.team_id:
        details.append(f"Team ID {_short_id(row.team_id)}")
    if row.channel_id:
        details.append(f"Channel ID {_short_id(row.channel_id)}")
    if row.user_aad_object_id:
        details.append(f"AAD {_short_id(row.user_aad_object_id)}")
    if override_name:
        details.append(f"原始名称 {raw_name}")
    details.append(f"会话 ID {_short_id(row.conversation_id)}")
    if is_validation:
        details.insert(0, "Teams App 验证产生，不建议作为正式通知目标")

    type_label = {
        "personal": "个人",
        "channel": "频道",
        "groupChat": "群聊",
    }.get(conv_type, conv_type or "未知")
    target_label = f"{type_label} | {display_name}"
    if is_validation:
        target_label = f"验证会话 | {display_name}"

    return {
        "display_name": display_name,
        "display_detail": " ｜ ".join(details),
        "target_label": target_label,
        "team_name": team_name,
        "channel_name": channel_name,
        "sender_name": sender_name,
        "is_validation_target": is_validation,
    }


def _conversation_out(row: TeamsBotConversation) -> TeamsBotConversationOut:
    return TeamsBotConversationOut.model_validate({
        "id": row.id,
        "conversation_id": row.conversation_id,
        "tenant_id": row.tenant_id,
        "team_id": row.team_id,
        "channel_id": row.channel_id,
        "conversation_type": row.conversation_type,
        "name": row.name,
        "display_name_override": row.display_name_override,
        "user_aad_object_id": row.user_aad_object_id,
        "user_name": row.user_name,
        "last_seen_at": row.last_seen_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        **_conversation_display(row),
    })


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
    target: TeamsBotConversation | None = None
    if activity_type in {"message", "conversationUpdate", "installationUpdate"}:
        try:
            target = upsert_conversation(db, activity)
        except Exception as exc:
            raise HTTPException(400, f"保存 Teams 会话失败：{exc}")
    if target and _should_send_welcome(activity) and not target.welcome_sent_at:
        try:
            send_text_message(target, _welcome_text())
            target.welcome_sent_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            raise HTTPException(400, f"Teams Bot welcome message failed: {exc}")

    if target and activity_type == "message" and _is_bot_command(activity):
        try:
            send_text_message(target, _command_reply_text())
        except Exception as exc:
            raise HTTPException(400, f"Teams Bot command reply failed: {exc}")
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
    rows = (
        db.query(TeamsBotConversation)
        .order_by(TeamsBotConversation.last_seen_at.desc(), TeamsBotConversation.id.desc())
        .all()
    )
    return [_conversation_out(row) for row in rows]


@router.put("/teams-bot/conversations/{conversation_pk}/display-name", response_model=TeamsBotConversationOut)
def update_teams_bot_conversation_display_name(
    conversation_pk: int,
    body: TeamsBotConversationNameIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    target = db.get(TeamsBotConversation, conversation_pk)
    if not target:
        raise HTTPException(404, "Teams Bot 目标不存在")
    target.display_name_override = body.display_name.strip()[:240]
    db.commit()
    db.refresh(target)
    return _conversation_out(target)


@router.post("/teams-bot/conversations/{conversation_pk}/test")
def test_teams_bot_conversation(
    conversation_pk: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    target = db.get(TeamsBotConversation, conversation_pk)
    if not target:
        raise HTTPException(404, "Teams Bot 目标不存在")
    display = _conversation_display(target)
    try:
        result = send_adaptive_card(
            target,
            title="92综合指数 Bot 测试",
            lines=[
                f"目标：{display['display_name']}",
                f"详情：{display['display_detail']}",
                "如果你能看到这条消息，说明 Bot 主动推送链路已经打通。",
                f"发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ],
            link_url=settings.teams_portal_url,
            link_label="系统链接",
        )
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "response": result}
