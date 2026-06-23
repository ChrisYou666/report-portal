from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import IndexNotificationConfig, TeamsBotConversation
from app.services.teams_bot import send_adaptive_card

INDEX_NOTIFICATION_OPTIONS = [
    {"code": "composite", "name": "92综合指数"},
    {"code": "agri", "name": "农业"},
    {"code": "futures", "name": "期货"},
    {"code": "industry", "name": "工业"},
    {"code": "livestock", "name": "牧业"},
    {"code": "commerce", "name": "商业"},
    {"code": "logistics", "name": "物流"},
    {"code": "dist", "name": "分配"},
    {"code": "russell", "name": "罗素骨干"},
    {"code": "chicago", "name": "芝加哥人力"},
    {"code": "env", "name": "环境生态"},
    {"code": "asset", "name": "资产扩张"},
    {"code": "estate", "name": "单数园子"},
    {"code": "dividend", "name": "分红"},
]


def ensure_index_notification_defaults(db: Session) -> list[IndexNotificationConfig]:
    existing = {
        row.index_code: row
        for row in db.query(IndexNotificationConfig).all()
    }
    for item in INDEX_NOTIFICATION_OPTIONS:
        if item["code"] not in existing:
            row = IndexNotificationConfig(
                index_code=item["code"],
                index_name=item["name"],
                enabled=False,
            )
            db.add(row)
            existing[item["code"]] = row
        else:
            existing[item["code"]].index_name = item["name"]
    db.commit()
    return (
        db.query(IndexNotificationConfig)
        .order_by(IndexNotificationConfig.id)
        .all()
    )


def build_indicator_url(index_code: str) -> str:
    parts = urlsplit(settings.teams_portal_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["index"] = index_code
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def send_index_notification(db: Session, config_id: int, force: bool = False) -> IndexNotificationConfig:
    cfg = db.get(IndexNotificationConfig, config_id)
    if not cfg:
        raise ValueError("指标通知配置不存在")
    cfg.last_run_at = datetime.utcnow()

    try:
        if not force and not cfg.enabled:
            cfg.last_status = "skipped"
            cfg.last_message = "通知未启用"
            db.commit()
            return cfg
        if not cfg.teams_conversation_id:
            raise RuntimeError("未选择 Teams Bot 目标")
        target = db.get(TeamsBotConversation, cfg.teams_conversation_id)
        if not target:
            raise RuntimeError("Teams Bot 目标不存在或已删除")

        snapshot = _build_index_snapshot(db, cfg.index_code, cfg.index_name)
        link = build_indicator_url(cfg.index_code)
        send_adaptive_card(
            target,
            title=f"{cfg.index_name} 指标通知",
            lines=snapshot,
            link_url=link,
            link_label="系统链接",
        )
        cfg.last_status = "success"
        cfg.last_message = "已发送 Teams Bot 通知"
    except Exception as exc:
        cfg.last_status = "failed"
        cfg.last_message = str(exc)
        db.commit()
        raise
    db.commit()
    db.refresh(cfg)
    return cfg


def preview_index_notification(db: Session, index_code: str, index_name: str) -> dict[str, Any]:
    return {
        "title": f"{index_name} 指标通知",
        "lines": _build_index_snapshot(db, index_code, index_name),
        "url": build_indicator_url(index_code),
    }


def _build_index_snapshot(db: Session, index_code: str, index_name: str) -> list[str]:
    try:
        from app.api.index_data import get_calculated_indices

        result = get_calculated_indices(months=3, db=db, _user=None)
    except Exception as exc:
        return [f"当前无法计算指标：{exc}"]

    if index_code == "composite":
        data = (result.get("composite") or {}).get("data") or []
    else:
        series = next((item for item in result.get("indices", []) if item.get("code") == index_code), None)
        if not series:
            return [f"当前系统没有找到 {index_name} 的指标数据。"]
        data = series.get("data") or []

    latest = _latest_value(data)
    previous = _previous_value(data, latest)
    if not latest:
        return [f"{index_name} 暂无可推送数据。"]

    lines = [
        f"指标：{index_name}",
        f"期间：{latest['year']}-{str(latest['month']).zfill(2)}",
        f"当前值：{latest['value']:.2f}",
    ]
    if previous:
        delta = latest["value"] - previous["value"]
        pct = (delta / abs(previous["value"]) * 100) if previous["value"] else None
        if pct is None:
            lines.append(f"较上期：{delta:+.2f}")
        else:
            lines.append(f"较上期：{delta:+.2f} ({pct:+.2f}%)")
    lines.append(f"发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return lines


def _latest_value(data: list[dict[str, Any]]) -> dict[str, Any] | None:
    for point in reversed(data):
        value = point.get("value")
        if value is not None:
            return {"year": point["year"], "month": point["month"], "value": float(value)}
    return None


def _previous_value(data: list[dict[str, Any]], latest: dict[str, Any] | None) -> dict[str, Any] | None:
    if latest is None:
        return None
    seen_latest = False
    for point in reversed(data):
        value = point.get("value")
        if value is None:
            continue
        same = point.get("year") == latest["year"] and point.get("month") == latest["month"]
        if same and not seen_latest:
            seen_latest = True
            continue
        if seen_latest:
            return {"year": point["year"], "month": point["month"], "value": float(value)}
    return None
