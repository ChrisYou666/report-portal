from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.cache import cache, TTL_INDEX_CALC, PFX_INDEX_CALC
from app.db import get_db
from app.models import IndexDataEntry, IndexDefinition, IndexSubMetric, SystemConfig, User

router = APIRouter(tags=["index-data"])

COMPOSITE_FORMULA_KEY = "composite_index_formula"
COMPOSITE_LABEL_KEY = "composite_index_label"

_SAFE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.+-*/()**  \t\n")
_SAFE_BUILTINS = {"abs": abs, "round": round, "max": max, "min": min, "pow": pow}


def _safe_eval(formula: str, variables: dict[str, float]) -> Optional[float]:
    """Evaluate a math formula string with the given variable bindings."""
    if not formula.strip():
        return None
    if not all(c in _SAFE_CHARS for c in formula):
        return None
    try:
        result = eval(formula, {"__builtins__": _SAFE_BUILTINS}, variables)
        return float(result)
    except Exception:
        return None


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


# ── Data Entry ────────────────────────────────────────────────

class DataEntryItem(BaseModel):
    sub_metric_id: int
    value: Optional[float] = None
    source: str = "manual"
    remark: str = ""


class DataEntryBatch(BaseModel):
    period_year: int
    period_month: int
    entries: list[DataEntryItem]


@router.get("/index-data/{year}/{month}")
def get_data_for_period(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entries = (
        db.query(IndexDataEntry)
        .filter_by(period_year=year, period_month=month)
        .all()
    )
    return [
        {
            "id": e.id,
            "sub_metric_id": e.sub_metric_id,
            "value": e.value,
            "source": e.source,
            "remark": e.remark,
            "updated_at": e.updated_at.isoformat(),
        }
        for e in entries
    ]


@router.put("/index-data")
def upsert_data(
    body: DataEntryBatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    if not 1 <= body.period_month <= 12:
        raise HTTPException(400, "period_month 必须在 1–12 之间")

    for item in body.entries:
        existing = (
            db.query(IndexDataEntry)
            .filter_by(
                sub_metric_id=item.sub_metric_id,
                period_year=body.period_year,
                period_month=body.period_month,
            )
            .first()
        )
        if existing:
            existing.value = item.value
            existing.source = item.source
            existing.remark = item.remark
        else:
            db.add(IndexDataEntry(
                sub_metric_id=item.sub_metric_id,
                period_year=body.period_year,
                period_month=body.period_month,
                value=item.value,
                source=item.source,
                remark=item.remark,
                created_by=user.username,
            ))
    db.commit()
    cache.delete_prefix(PFX_INDEX_CALC)
    return {"ok": True}


# ── Calculation ───────────────────────────────────────────────

@router.get("/index-calc")
def get_calculated_indices(
    months: int = 12,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Returns per-period calculated values for every active index
    and the composite (综合指数) over the last N months.
    """
    key = f"{PFX_INDEX_CALC}{months}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    periods = _prev_months(max(1, min(months, 60)))

    # Load all active index definitions (with sub_metrics via selectin)
    indices = (
        db.query(IndexDefinition)
        .filter_by(is_active=True)
        .order_by(IndexDefinition.sort_order, IndexDefinition.id)
        .all()
    )

    # Collect all sub_metric ids we care about
    all_sm_ids = [sm.id for idx in indices for sm in idx.sub_metrics]

    # Load all relevant data entries in one query
    entries = (
        db.query(IndexDataEntry)
        .filter(
            IndexDataEntry.sub_metric_id.in_(all_sm_ids),
            IndexDataEntry.period_year.in_({p[0] for p in periods}),
        )
        .all()
    )

    # Build lookup: sub_metric_id → {(year, month) → value}
    entry_map: dict[int, dict[tuple[int, int], Optional[float]]] = {}
    for e in entries:
        entry_map.setdefault(e.sub_metric_id, {})[(e.period_year, e.period_month)] = e.value

    # Calculate each index per period
    index_series: list[dict] = []
    # period → {index_code → computed value}
    period_index_values: dict[tuple[int, int], dict[str, Optional[float]]] = {p: {} for p in periods}

    for idx in indices:
        series_data = []
        for period in periods:
            variables: dict[str, float] = {}
            for sm in idx.sub_metrics:
                if sm.fixed_value is not None:
                    # 固定值优先，不依赖月度录入
                    variables[sm.code] = sm.fixed_value
                else:
                    val = entry_map.get(sm.id, {}).get(period)
                    if val is not None:
                        variables[sm.code] = val
            computed = _safe_eval(idx.formula, variables) if variables else None
            period_index_values[period][idx.code] = computed
            series_data.append({"year": period[0], "month": period[1], "value": computed})

        index_series.append({
            "id": idx.id,
            "code": idx.code,
            "name": idx.name,
            "formula": idx.formula,
            "granularity": idx.granularity or "monthly",
            "sub_metrics": [
                {"id": sm.id, "code": sm.code, "name": sm.name, "unit": sm.unit}
                for sm in idx.sub_metrics
            ],
            "data": series_data,
        })

    # Calculate composite per period
    formula_cfg = db.get(SystemConfig, COMPOSITE_FORMULA_KEY)
    label_cfg = db.get(SystemConfig, COMPOSITE_LABEL_KEY)
    composite_formula = formula_cfg.value if formula_cfg else ""
    composite_label = label_cfg.value if label_cfg else "综合指数"

    composite_data = []
    for period in periods:
        idx_vals = period_index_values[period]
        non_null = {k: v for k, v in idx_vals.items() if v is not None}
        composite_val = _safe_eval(composite_formula, non_null) if composite_formula and non_null else None
        composite_data.append({"year": period[0], "month": period[1], "value": composite_val})

    result = {
        "composite": {
            "label": composite_label,
            "formula": composite_formula,
            "data": composite_data,
        },
        "indices": index_series,
    }
    return cache.set(key, result, TTL_INDEX_CALC)


@router.get("/index-calc/sub-metrics/{year}/{month}")
def get_sub_metric_detail(
    year: int,
    month: int,
    index_id: int,
    months: int = 12,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Return raw sub-metric time-series for a specific index (drill-down)."""
    idx = db.get(IndexDefinition, index_id)
    if not idx:
        raise HTTPException(404, "指标不存在")

    periods = _prev_months(max(1, min(months, 60)))
    sm_ids = [sm.id for sm in idx.sub_metrics]

    entries = (
        db.query(IndexDataEntry)
        .filter(
            IndexDataEntry.sub_metric_id.in_(sm_ids),
            IndexDataEntry.period_year.in_({p[0] for p in periods}),
        )
        .all()
    )

    entry_map: dict[int, dict[tuple[int, int], Optional[float]]] = {}
    for e in entries:
        entry_map.setdefault(e.sub_metric_id, {})[(e.period_year, e.period_month)] = e.value

    result = []
    for sm in idx.sub_metrics:
        data = [
            {"year": p[0], "month": p[1], "value": entry_map.get(sm.id, {}).get(p)}
            for p in periods
        ]
        result.append({
            "id": sm.id,
            "code": sm.code,
            "name": sm.name,
            "unit": sm.unit,
            "data": data,
        })

    return {"index_name": idx.name, "sub_metrics": result}
