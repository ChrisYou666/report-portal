from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests
from jose import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TeamsBotConversation

BOT_OPENID_CONFIG_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
BOT_SCOPE = "https://api.botframework.com/.default"

_openid_cache: dict[str, Any] = {"expires_at": 0.0, "jwks": None}
_token_cache: dict[str, Any] = {"expires_at": 0.0, "token": ""}


def verify_incoming_token(authorization: str | None) -> None:
    """Verify Bot Framework JWT when production validation is enabled."""
    if not settings.teams_bot_validate_incoming:
        return
    if not settings.teams_bot_app_id:
        raise ValueError("TEAMS_BOT_APP_ID 未配置，无法校验 Teams Bot 请求")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("缺少 Bot Framework Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    jwks = _get_bot_jwks()
    jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=settings.teams_bot_app_id,
        options={"verify_iss": False},
    )


def _get_bot_jwks() -> dict[str, Any]:
    now = time.time()
    if _openid_cache["jwks"] and now < _openid_cache["expires_at"]:
        return _openid_cache["jwks"]
    meta = requests.get(BOT_OPENID_CONFIG_URL, timeout=10).json()
    jwks = requests.get(meta["jwks_uri"], timeout=10).json()
    _openid_cache.update({"jwks": jwks, "expires_at": now + 3600})
    return jwks


def upsert_conversation(db: Session, activity: dict[str, Any]) -> TeamsBotConversation:
    conversation = activity.get("conversation") or {}
    conversation_id = conversation.get("id") or ""
    service_url = activity.get("serviceUrl") or ""
    if not conversation_id or not service_url:
        raise ValueError("Teams activity 缺少 conversation.id 或 serviceUrl")

    channel_data = activity.get("channelData") or {}
    tenant = channel_data.get("tenant") or {}
    team = channel_data.get("team") or {}
    channel = channel_data.get("channel") or {}
    sender = activity.get("from") or {}

    row = (
        db.query(TeamsBotConversation)
        .filter(TeamsBotConversation.conversation_id == conversation_id)
        .first()
    )
    if row is None:
        row = TeamsBotConversation(conversation_id=conversation_id, service_url=service_url)
        db.add(row)

    row.service_url = service_url
    row.tenant_id = tenant.get("id") or ""
    row.team_id = team.get("id") or ""
    row.channel_id = channel.get("id") or ""
    row.conversation_type = conversation.get("conversationType") or ""
    row.name = _conversation_label(conversation, team, channel, sender)
    row.user_aad_object_id = sender.get("aadObjectId") or ""
    row.user_name = sender.get("name") or ""
    row.raw_activity = json.dumps(activity, ensure_ascii=False)
    row.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def _conversation_label(
    conversation: dict[str, Any],
    team: dict[str, Any],
    channel: dict[str, Any],
    sender: dict[str, Any],
) -> str:
    conv_type = conversation.get("conversationType") or ""
    team_name = team.get("name") or ""
    channel_name = channel.get("name") or ""
    sender_name = sender.get("name") or ""
    if conv_type == "channel":
        return " / ".join([p for p in [team_name, channel_name] if p]) or conversation.get("name") or "Teams 频道"
    if conv_type == "personal":
        return sender_name or conversation.get("name") or "个人聊天"
    return conversation.get("name") or sender_name or conv_type or "Teams 会话"


def send_adaptive_card(
    conversation: TeamsBotConversation,
    title: str,
    lines: list[str],
    link_url: str | None = None,
    link_label: str = "打开系统页面",
) -> dict[str, Any]:
    if not settings.teams_bot_app_id or not settings.teams_bot_app_password:
        raise RuntimeError("Teams Bot App ID/Password 未配置，暂不能发送 Bot 主动消息")

    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "size": "Medium", "weight": "Bolder", "wrap": True, "text": title},
    ]
    body.extend({"type": "TextBlock", "wrap": True, "text": line} for line in lines if line)
    actions: list[dict[str, Any]] = []
    if link_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": link_label,
            "url": link_url,
        })

    card_content: dict[str, Any] = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": body,
    }
    if actions:
        card_content["actions"] = actions

    payload = {
        "type": "message",
        "from": {"id": settings.teams_bot_app_id, "name": settings.teams_bot_name},
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": card_content,
        }],
    }
    return _post_activity(conversation, payload)


def send_text_message(conversation: TeamsBotConversation, text: str) -> dict[str, Any]:
    if not settings.teams_bot_app_id or not settings.teams_bot_app_password:
        raise RuntimeError("Teams Bot App ID/Password is not configured")

    payload = {
        "type": "message",
        "from": {"id": settings.teams_bot_app_id, "name": settings.teams_bot_name},
        "text": text,
    }
    return _post_activity(conversation, payload)


def _post_activity(conversation: TeamsBotConversation, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{conversation.service_url.rstrip('/')}/v3/conversations/{quote(conversation.conversation_id, safe='')}/activities"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {_get_connector_token()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Teams Bot 发送失败：HTTP {response.status_code} {response.text}")
    return {"status_code": response.status_code, "body": response.text}


def _get_connector_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    response = requests.post(
        f"https://login.microsoftonline.com/{settings.teams_bot_tenant_id or 'botframework.com'}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.teams_bot_app_id,
            "client_secret": settings.teams_bot_app_password,
            "scope": BOT_SCOPE,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"获取 Teams Bot token 失败：HTTP {response.status_code} {response.text}")
    payload = response.json()
    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    _token_cache.update({"token": token, "expires_at": now + expires_in - 60})
    return token
