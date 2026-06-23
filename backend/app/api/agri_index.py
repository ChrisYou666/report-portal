from __future__ import annotations

import calendar
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db import get_db
from app.models import IndexDataEntry, IndexSubMetric, User

router = APIRouter(tags=["agri-index"])

# 财年起始月（9月）
FISCAL_START_MONTH = 9


def _fiscal_year_start(year: int, month: int) -> date:
    """返回给定年月所在财年的起始日期（9月1日）。"""
    fy = year if month >= FISCAL_START_MONTH else year - 1
    return date(fy, FISCAL_START_MONTH, 1)


def _prev_months(n: int) -> list[tuple[int, int]]:
    today = date.today()
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


def _compute_agri_cumulative(months: int, db: Session) -> list[dict]:
    """
    返回最近 N 个月的财年累计产量（吨）。
    数据源: stg_zest_blockc.ntqty（kg），除以 1000 转为吨。
    累计区间: 当月所在财年的 9月1日 → 当月最后一天。
    """
    periods = _prev_months(max(1, min(months, 60)))
    results: list[dict] = []

    for yr, mo in periods:
        fy_start = _fiscal_year_start(yr, mo)
        last_day = calendar.monthrange(yr, mo)[1]
        period_end = date(yr, mo, last_day)

        try:
            row = db.execute(
                text("""
                    SELECT COALESCE(SUM(ntqty), 0) / 1000.0
                    FROM stg_zest_blockc
                    WHERE crdat >= :fy_start AND crdat <= :period_end
                """),
                {"fy_start": fy_start, "period_end": period_end},
            ).fetchone()
        except Exception:
            return []

        cumulative_tons = round(float(row[0]) if row and row[0] is not None else 0.0, 2)
        results.append({
            "year": yr,
            "month": mo,
            "cumulative_tons": cumulative_tons,
            # 兼容旧接口字段：value 仍为累计吨数，调用方可按需自行组合公式
            "value": cumulative_tons,
        })

    return results


@router.get("/agri-index/production/preview")
def preview_agri_production(
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "analyst")),
):
    """预览农业财年累计产量（不写入数据库）。"""
    data = _compute_agri_cumulative(months, db)
    if not data:
        raise HTTPException(500, "查询失败，请检查数据库连接或 stg_zest_blockc 表是否存在")
    return data


@router.post("/agri-index/production/sync")
def sync_agri_production(
    sub_metric_id: int = Query(..., description="写入目标分项 ID（对应累计产量变量）"),
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    """
    将农业财年累计产量（吨）写入 IndexDataEntry。
    公式计算由 IndexDefinition.formula 负责，此处只存原始累计量。
    典型公式: prod / budget * 100 + 100
    """
    sm = db.get(IndexSubMetric, sub_metric_id)
    if not sm:
        raise HTTPException(404, "分项不存在")

    data = _compute_agri_cumulative(months, db)
    if not data:
        raise HTTPException(500, "查询失败，请检查数据库连接或 stg_zest_blockc 表是否存在")

    for item in data:
        existing = (
            db.query(IndexDataEntry)
            .filter_by(
                sub_metric_id=sub_metric_id,
                period_year=item["year"],
                period_month=item["month"],
            )
            .first()
        )
        if existing:
            existing.value = item["cumulative_tons"]
            existing.source = "agri_db"
            existing.remark = f"财年累计产量 {item['cumulative_tons']:.0f} 吨"
            existing.updated_at = datetime.utcnow()
        else:
            db.add(IndexDataEntry(
                sub_metric_id=sub_metric_id,
                period_year=item["year"],
                period_month=item["month"],
                value=item["cumulative_tons"],
                source="agri_db",
                remark=f"财年累计产量 {item['cumulative_tons']:.0f} 吨",
                created_by=user.username,
            ))

    db.commit()
    return {"synced": len(data), "sub_metric_id": sub_metric_id, "items": data}
