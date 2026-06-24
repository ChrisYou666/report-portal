from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

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

MOCK_JUNE_TARGETS: dict[str, float] = {
    "futures": 172,
    "industry": 185,
    "livestock": 173,
    "commerce": 176,
    "logistics": 171,
    "dist": 174,
    "russell": 178,
    "chicago": 172,
    "env": 175,
    "asset": 183,
    "estate": 180,
    "dividend": 171,
}

FY_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]
FY_START_MONTH = 9


def force_daily_schedule(cfg: IndexNotificationConfig) -> None:
    cfg.cron_day = "*"
    cfg.cron_month = "*"
    cfg.cron_dow = "*"


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
            row = existing[item["code"]]
            row.index_name = item["name"]
            force_daily_schedule(row)
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


def build_teams_tab_url(index_code: str, index_name: str) -> str:
    web_url = build_indicator_url(index_code)
    if not settings.teams_deep_link_enabled or not settings.teams_app_id:
        return web_url

    context = json.dumps({"subEntityId": index_code}, ensure_ascii=False, separators=(",", ":"))
    query = urlencode({
        "webUrl": web_url,
        "label": f"{index_name} 指数",
        "context": context,
    })
    app_id = quote(settings.teams_app_id, safe="")
    entity_id = quote(settings.teams_tab_entity_id or "indicator", safe="")
    return f"https://teams.microsoft.com/l/entity/{app_id}/{entity_id}?{query}"


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
        link = build_teams_tab_url(cfg.index_code, cfg.index_name)
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
        "url": build_teams_tab_url(index_code, index_name),
    }


def _build_index_snapshot(db: Session, index_code: str, index_name: str) -> list[str]:
    try:
        from app.api.index_data import get_calculated_indices

        result = get_calculated_indices(months=24, db=db, _user=None)
    except Exception as exc:
        return _build_dashboard_fallback_snapshot(index_code, index_name, f"当前无法计算真实指标：{exc}")

    if index_code == "composite":
        data = (result.get("composite") or {}).get("data") or []
    else:
        series = next((item for item in result.get("indices", []) if item.get("code") == index_code), None)
        if not series:
            return _build_dashboard_fallback_snapshot(index_code, index_name)
        data = series.get("data") or []

    latest = _latest_value(data)
    previous = _previous_value(data, latest)
    if not latest:
        return _build_dashboard_fallback_snapshot(index_code, index_name)

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


def _build_dashboard_fallback_snapshot(index_code: str, index_name: str, reason: str | None = None) -> list[str]:
    data = _dashboard_fallback_series(index_code)
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
            lines.append(f"较上月：{delta:+.2f}")
        else:
            lines.append(f"较上月：{delta:+.2f} ({pct:+.2f}%)")
    lines.append("口径：指数看板财年视图")
    if reason:
        lines.append(reason)
    lines.append(f"发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return lines


def _dashboard_fallback_series(index_code: str) -> list[dict[str, Any]]:
    today = datetime.now()
    available_months = set(_prev_months(24, today))
    current_ym = (today.year, today.month)
    child_codes = [item["code"] for item in INDEX_NOTIFICATION_OPTIONS if item["code"] != "composite"]

    if index_code == "composite":
        child_series = [_dashboard_fallback_series(code) for code in child_codes]
        data: list[dict[str, Any]] = []
        for idx, month in enumerate(FY_MONTHS):
            year = _fy_month_year(month, today)
            vals = [series[idx]["value"] for series in child_series if series[idx]["value"] is not None]
            value = round(sum(vals) / len(vals), 2) if vals else None
            data.append({"year": year, "month": month, "value": value})
        return data

    index_pos = child_codes.index(index_code) if index_code in child_codes else 0
    june_target = MOCK_JUNE_TARGETS.get(index_code, 165)
    data = []
    for month in FY_MONTHS:
        year = _fy_month_year(month, today)
        value = None
        if (year, month) in available_months and (year, month) != current_ym:
            fy_pos = (month - FY_START_MONTH + 12) % 12
            fy_year = year if month >= FY_START_MONTH else year - 1
            seed = (index_pos + 1) * 7919 + fy_year * 31 + fy_pos * 113
            value = _mock_fy_value(seed, fy_pos, june_target)
        data.append({"year": year, "month": month, "value": value})
    return data


def _prev_months(n: int, today: datetime) -> list[tuple[int, int]]:
    year, month = today.year, today.month
    result: list[tuple[int, int]] = []
    for _ in range(n):
        result.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(result))


def _fy_month_year(month: int, today: datetime) -> int:
    fy_start_year = today.year if today.month >= FY_START_MONTH else today.year - 1
    return fy_start_year if month >= FY_START_MONTH else fy_start_year + 1


def _mock_fy_value(seed: int, fy_pos: int, june_target: float) -> float:
    base = 103
    progress = min(fy_pos / 8, 1)
    trend = base + (june_target - base) * progress
    if fy_pos >= 8:
        return round(june_target * 10) / 10

    rng = (seed + fy_pos * 997) & 0xFFFFFFFF

    def next_random() -> float:
        nonlocal rng
        rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
        return rng / 0xFFFFFFFF

    noise = (next_random() - 0.3) * 7
    return round((trend + noise) * 10) / 10


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
